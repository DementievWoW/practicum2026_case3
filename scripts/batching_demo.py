"""
@file batching_demo.py
@brief Наглядная демонстрация continuous batching на «псевдо-vLLM».

@details
    Показывает, ПОЧЕМУ одна копия модели обрабатывает пачку запросов
    за один проход, а не каждый по отдельности.

    Симуляция (упрощённо, но честно по сути):
      - «проход модели» (weight_load_s) — доминирующая задержка,
        потому что LLM memory-bound: веса грузятся из GPU-памяти ОДИН раз
        на батч. Это и есть узкое место.
      - max_batch=1  → naive serving (каждый запрос = свой проход);
      - max_batch=32 → continuous batching (запросы копятся в окно и
        обрабатываются пачкой за один проход).

    Также показывает: 2 модели (Qwen-32B генератор + Qwen-7B судья) —
    это 2 НЕЗАВИСИМЫХ эндпоинта/очереди, разные веса нельзя смешать
    в один батч.

    Запуск:  python scripts/batching_demo.py
"""

from __future__ import annotations

import asyncio
import time

_T0 = time.time()


def ts() -> float:
    """@brief Секунды от старта (для таймлайна в логах)."""
    return time.time() - _T0


class MockVLLMServer:
    """
    @brief Псевдо-vLLM: очередь + continuous batching.
    @param name           Имя модели (для логов).
    @param pass_s         Время ОДНОГО прохода модели (на весь батч). Доминирует.
    @param max_batch      Максимум запросов в батче (1 = naive, без батчинга).
    @param max_wait_s     Окно ожидания набора батча.
    @param log            Логировать ли формирование батчей.
    """

    def __init__(self, name, pass_s, max_batch=32, max_wait_s=0.01, log=True):
        self.name = name
        self.pass_s = pass_s
        self.max_batch = max_batch
        self.max_wait_s = max_wait_s
        self.log = log
        self.queue: asyncio.Queue = asyncio.Queue()
        self.passes = 0          # сколько проходов модели сделано
        self.served = 0          # сколько запросов обслужено
        self._task = None

    async def start(self):
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()

    async def _loop(self):
        """@brief Цикл сервера: набирает батч и обрабатывает за один проход."""
        while True:
            req = await self.queue.get()           # ждём первый запрос
            batch = [req]
            # копим окно: добираем до max_batch или пока есть запросы
            while len(batch) < self.max_batch:
                try:
                    nxt = await asyncio.wait_for(self.queue.get(), timeout=self.max_wait_s)
                    batch.append(nxt)
                except asyncio.TimeoutError:
                    break
            # ── ОДИН проход модели на ВЕСЬ батч (веса грузятся раз) ──
            self.passes += 1
            self.served += len(batch)
            if self.log:
                names = ", ".join(p for p, _ in batch[:4])
                more = f" +{len(batch)-4}" if len(batch) > 4 else ""
                print(f"[t={ts():.3f}] {self.name}: проход #{self.passes} "
                      f"— батч {len(batch)} [{names}{more}] (веса грузятся 1 раз)")
            await asyncio.sleep(self.pass_s)        # время прохода
            for _, fut in batch:
                if not fut.done():
                    fut.set_result("ok")

    async def infer(self, prompt: str):
        """@brief Клиентский вызов — кладёт в очередь и ждёт результат батча."""
        fut = asyncio.get_event_loop().create_future()
        await self.queue.put((prompt, fut))
        return await fut


async def bench(server: MockVLLMServer, n: int, label: str) -> float:
    """@brief Шлёт n одновременных запросов, меряет общее время."""
    await server.start()
    t = time.time()
    await asyncio.gather(*[server.infer(f"req{i}") for i in range(n)])
    dt = time.time() - t
    await server.stop()
    print(f"  → {label}: {n} запросов за {dt:.3f}с, "
          f"проходов модели: {server.passes}\n")
    return dt


async def main():
    N = 20
    PASS = 0.10  # время одного прохода модели (сек), одинаково для честности

    print("=" * 64)
    print(f"ЭКСПЕРИМЕНТ: {N} судей, один проход модели = {PASS*1000:.0f} мс")
    print("=" * 64)

    print("\n### 1. NAIVE (max_batch=1) — каждый запрос свой проход ###")
    naive = MockVLLMServer("Qwen-7B[naive]", pass_s=PASS, max_batch=1, log=False)
    t_naive = await bench(naive, N, "naive")

    print("### 2. CONTINUOUS BATCHING (max_batch=32) — пачкой ###")
    batched = MockVLLMServer("Qwen-7B[batch]", pass_s=PASS, max_batch=32)
    t_batch = await bench(batched, N, "batched")

    print(f"⚡ Ускорение: {t_naive / t_batch:.1f}× "
          f"(одна копия модели, но {N} судей за ~один проход)\n")

    # ── 2 модели = 2 независимых батча ──
    print("=" * 64)
    print("2 МОДЕЛИ = 2 НЕЗАВИСИМЫХ ЭНДПОИНТА (разные веса, разные батчи)")
    print("=" * 64)
    gen = MockVLLMServer("Qwen-32B(генератор)", pass_s=0.20, max_batch=32)
    judge = MockVLLMServer("Qwen-7B(судья)", pass_s=0.10, max_batch=32)
    await gen.start()
    await judge.start()
    t = time.time()
    # 10 сессий: каждая дёргает И генератор, И судью — летят в РАЗНЫЕ очереди
    await asyncio.gather(
        *[gen.infer(f"gen(s{i})") for i in range(10)],
        *[judge.infer(f"judge(s{i})") for i in range(10)],
    )
    print(f"\n  → 10 ген + 10 судей за {time.time()-t:.3f}с")
    print(f"    32B-эндпоинт: {gen.passes} проход(ов), {gen.served} запросов")
    print(f"    7B-эндпоинт:  {judge.passes} проход(ов), {judge.served} запросов")
    print("    (генератор и судья батчатся РАЗДЕЛЬНО — нельзя смешать веса)")
    await gen.stop()
    await judge.stop()


if __name__ == "__main__":
    asyncio.run(main())
