# Build your gen AI–based text-to-SQL application using RAG, powered by Amazon Bedrock (Claude 3 Sonnet + Titan)

- **Status:** verified
- **Тип:** blog (vendor tutorial)
- **Канонический URL:** https://aws.amazon.com/blogs/machine-learning/build-your-gen-ai-based-text-to-sql-application-using-rag-powered-by-amazon-bedrock-claude-3-sonnet-and-amazon-titan-for-embedding/
- **Год / venue:** 18 марта 2025, AWS Machine Learning Blog
- **Автор:** Rajendra Choudhary

## Что это
Туториал AWS: как собрать NL→SQL приложение на Amazon Bedrock с RAG. Claude 3.5 Sonnet генерирует SQL, Amazon Titan делает эмбеддинги для семантического поиска по метаданным схемы, фронтенд — Streamlit. Архитектура: метаданные таблиц лежат в JSON, конвертируются в vector embeddings, по similarity-search достаются релевантные куски схемы и подаются в Claude как контекст.

## Почему релевантно
Канонический industrial reference-pattern для нашего сценария: схема как контекст через retrieval, LLM генерирует SQL, всё на managed-сервисах. Сравним с premsql / base-sql как «cloud-managed» альтернатива.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18, URL https://aws.amazon.com/blogs/machine-learning/build-your-gen-ai-based-text-to-sql-application-using-rag-powered-by-amazon-bedrock-claude-3-sonnet-and-amazon-titan-for-embedding/
- Цитаты:
  - "This solution allows users to ask questions in natural language and then generates a SQL query for the user's request"
  - "off-the-shelf LLMs can't be used without some modification" (про необходимость доменного контекста)
  - "The architecture stores table metadata in JSON files, converts them to vector embeddings, and uses similarity search to retrieve relevant schema information before passing it to Claude for SQL generation"
