-- ════════════════════════════════════════════════════════════════════════════
-- PII-OVERLAY — СИНТЕТИЧЕСКИЕ таблицы с чувствительными данными.
--
-- ЗАЧЕМ:
--   В выданной мета-схеме GreenData (data_model.sql) нет явных PII-колонок
--   (password/passport/snils) — это банковская low-code мета-схема финансовых
--   объектов. Но банк выдаёт кредиты физлицам → клиенты с ПДн логически
--   существуют (просто обезличены/в другом контуре).
--
--   Этот overlay добавляет к sandbox таблицы с ЯВНЫМИ чувствительными полями,
--   чтобы:
--     1. было на чём демонстрировать класс DIRECT_SENSITIVE (паспорт, карта);
--     2. был полигон для правила R009 (sensitive columns) и checksum-проверок.
--
-- ⚠️  ВСЕ ДАННЫЕ СИНТЕТИЧЕСКИЕ. Реальный список чувствительных колонок
--     заказчика — уточняется (вопрос кураторам). Когда ответят — заменить.
--
-- Префикс sim_ помечает синтетику.
-- ════════════════════════════════════════════════════════════════════════════

-- Физлицо-заёмщик (связан с credit_contract как клиент)
CREATE TABLE public.sim_client (
    id            bigint NOT NULL,
    full_name     character varying(500),   -- ФИО (ПДн)
    passport      character varying(20),     -- серия+номер паспорта (ПДн)
    snils         character varying(14),     -- СНИЛС (ПДн, 152-ФЗ)
    inn           character varying(12),     -- ИНН физлица (ПДн)
    phone         character varying(20),     -- телефон (ПДн)
    email         character varying(200),    -- email (ПДн)
    birth_date    date,                       -- дата рождения (ПДн)
    address       character varying(1000)    -- адрес регистрации (ПДн)
);
COMMENT ON TABLE public.sim_client IS 'СИНТЕТИКА: Клиент-физлицо (заёмщик)';
COMMENT ON COLUMN public.sim_client.passport IS 'Паспорт (серия и номер)';
COMMENT ON COLUMN public.sim_client.snils IS 'СНИЛС';
COMMENT ON COLUMN public.sim_client.inn IS 'ИНН физлица';

-- Платёжная карта (связана с клиентом)
CREATE TABLE public.sim_payment_card (
    id           bigint NOT NULL,
    client_id    bigint,
    card_number  character varying(19),   -- номер карты (PCI DSS)
    cvv          character varying(4),     -- CVV (НЕЛЬЗЯ хранить!)
    expiry       character varying(7),     -- срок действия
    pan          character varying(19)     -- PAN
);
COMMENT ON TABLE public.sim_payment_card IS 'СИНТЕТИКА: Платёжная карта клиента';
COMMENT ON COLUMN public.sim_payment_card.card_number IS 'Номер карты';
COMMENT ON COLUMN public.sim_payment_card.cvv IS 'CVV код';

-- Учётная запись сотрудника (креды)
CREATE TABLE public.sim_employee_account (
    id             bigint NOT NULL,
    login          character varying(100),
    password_hash  character varying(256),   -- хеш пароля (кред)
    api_token      character varying(256),    -- API-токен (кред)
    full_name      character varying(500),
    phone          character varying(20)
);
COMMENT ON TABLE public.sim_employee_account IS 'СИНТЕТИКА: Учётная запись сотрудника';
COMMENT ON COLUMN public.sim_employee_account.password_hash IS 'Хеш пароля';
COMMENT ON COLUMN public.sim_employee_account.api_token IS 'API токен доступа';

-- Закомментированные FK (как в основном дампе)
-- ALTER TABLE ONLY public.sim_payment_card
--     ADD CONSTRAINT fk_sim_card_client FOREIGN KEY (client_id) REFERENCES public.sim_client(id);
