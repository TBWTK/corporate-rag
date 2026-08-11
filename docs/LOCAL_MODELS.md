---
title: Локальный запуск на macOS и Windows
type: guide
status: complete
updated: 2026-08-11
---

# Локальный запуск на macOS и Windows

Этот режим запускает документы, embeddings, ответы и разбор скриншотов на ноутбуке заказчика.
GigaChat, облачный API и ключи не нужны. Приложение и PostgreSQL работают в Docker Desktop, а
Ollama — нативно на компьютере, чтобы использовать доступное аппаратное ускорение.

## Что потребуется

- 32 ГБ RAM и не менее 25 ГБ свободного места;
- macOS Sonoma 14+ либо Windows 10 22H2/Windows 11;
- [Docker Desktop](https://www.docker.com/products/docker-desktop/);
- [Ollama](https://ollama.com/download);
- папка проекта или `git clone https://github.com/TBWTK/corporate-rag.git`.

Рекомендуемый профиль для Intel Core Ultra 7 и 32 ГБ RAM:

| Задача | Модель | Размер загрузки | Зачем |
| --- | --- | ---: | --- |
| Ответы | `qwen3:8b` | 5,2 ГБ | русский язык, инструкции и JSON |
| Поиск | `mxbai-embed-large` | 670 МБ | нативные 1024 измерения для текущего pgvector |
| Скриншоты | `qwen2.5vl:3b` | 3,2 ГБ | страницы PDF/DOCX с интерфейсом |

На Intel-ноутбуке Ollama может использовать CPU, поэтому первый ответ и разбор страниц могут
занимать минуты. Если это слишком медленно, замените `qwen3:8b` на `qwen3:4b` одновременно в
команде `ollama pull` и `.env`. На Apple Silicon Ollama использует Metal; Intel Mac работает на CPU.

## 1. Установите Ollama и Docker Desktop

### macOS

1. Установите [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
   и дождитесь статуса `Docker Desktop is running`.
2. Скачайте `ollama.dmg`, перенесите Ollama в `Applications` и один раз откройте приложение.
3. Откройте Terminal и разрешите контейнерам обращаться к Ollama:

   ```bash
   launchctl setenv OLLAMA_HOST "0.0.0.0:11434"
   launchctl setenv OLLAMA_NO_CLOUD "1"
   ```

4. В меню Ollama нажмите `Quit Ollama`, затем снова откройте его из `Applications`.
5. Проверьте локальный сервер:

   ```bash
   curl http://localhost:11434/api/version
   ```

### Windows

1. Установите [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
   с WSL 2 backend и дождитесь статуса `Docker Desktop is running`.
2. Запустите `OllamaSetup.exe`. Ollama появится в системном трее, а команда `ollama` — в новом
   PowerShell.
3. Откройте PowerShell и сохраните настройки локального сервера:

   ```powershell
   [Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
   [Environment]::SetEnvironmentVariable("OLLAMA_NO_CLOUD", "1", "User")
   ```

4. Полностью завершите Ollama через значок в трее и запустите снова из меню Start.
5. Проверьте сервер:

   ```powershell
   Invoke-RestMethod http://localhost:11434/api/version
   ```

`OLLAMA_HOST=0.0.0.0:11434` нужен только для связи Docker Desktop → Ollama. Не публикуйте порт
`11434` через роутер, VPN или внешний firewall. На публичной сети запретите входящие подключения к
Ollama; приложение рассчитано на один доверенный ноутбук.

## 2. Загрузите модели

В Terminal или PowerShell выполните одинаковые команды:

```text
ollama pull qwen3:8b
ollama pull mxbai-embed-large
ollama pull qwen2.5vl:3b
ollama list
```

Дождитесь завершения каждой загрузки. Аккаунт Ollama и API-ключ для локальных моделей не нужны.
Если корпус содержит только обычный текст без скриншотов, vision можно отключить: не скачивайте
`qwen2.5vl:3b` и позже поставьте `VISION_INGESTION_ENABLED=false`.

## 3. Подготовьте проект и `.env`

Откройте папку проекта в Terminal/PowerShell.

macOS:

```bash
cp .env.ollama.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.ollama.example .env
```

Шаблон уже готов к работе. В нём должны остаться ключевые значения:

```dotenv
RAG_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
GENERATION_MODEL=qwen3:8b
EMBEDDING_MODEL=mxbai-embed-large
EMBEDDING_DIMENSION=1024
OLLAMA_VISION_MODEL=qwen2.5vl:3b
OLLAMA_THINK=false
OLLAMA_SERIALIZE_REQUESTS=true
```

Не добавляйте `GIGACHAT_API_KEY`: локальному режиму он не нужен. Не меняйте
`EMBEDDING_DIMENSION=1024` — такая размерность зафиксирована в текущей схеме PostgreSQL.

## 4. Запустите и проверьте

Команды одинаковы на macOS и Windows:

```text
docker compose up --build -d
docker compose ps
docker compose run --rm --no-deps api python -m rag_app.local_check
```

Успешная проверка заканчивается строками `LOCAL CHECK OK`, `Embedding dimension: 1024` и именами
моделей. Она проверяет путь из Docker до Ollama, наличие весов, реальный embedding и короткий ответ.
Vision-модель проверяется по списку; фактический разбор изображения начнётся при загрузке
PDF/DOCX со скриншотами.

Откройте [http://localhost:8000](http://localhost:8000). Создайте пространство, загрузите сначала
один небольшой TXT/DOCX и дождитесь статуса `Готов`. Задайте вопрос, ответ на который явно есть в
файле, и раскройте источник. Затем загрузите визуальную инструкцию: её страницы должны появиться в
визуальном туториале под ответом.

## 5. Ежедневные команды

```text
docker compose logs -f api worker   # диагностика приложения
ollama ps                           # какие модели сейчас в RAM/на GPU
docker compose stop                 # остановить, сохранив документы и БД
docker compose start                # запустить снова без сборки
docker compose down                 # удалить контейнеры, но сохранить volumes
```

После обновления кода выполните `docker compose up --build -d`. Модели Ollama обновляются повторной
командой `ollama pull <model>`.

## Смена модели и существующие документы

Embeddings разных моделей несовместимы, даже если обе имеют 1024 измерения. После смены
`EMBEDDING_MODEL` удалите и повторно загрузите все документы. Для чистого тестового запуска можно
удалить локальные volumes, но эта команда необратимо удаляет БД и загруженные файлы:

```text
docker compose down -v
docker compose up --build -d
```

Не выполняйте `down -v`, если в приложении есть единственная копия нужных документов. При переходе
с GigaChat на Ollama безопаснее сохранить исходные файлы и создать чистый индекс.

## Если не запускается

| Симптом | Что сделать |
| --- | --- |
| `LOCAL CHECK FAILED: Не удалось подключиться` | Проверьте Ollama, `api/version`, `OLLAMA_HOST`, перезапустите Ollama и Docker Desktop |
| `Ollama не нашёл модель` | Выполните указанную `ollama pull ...`, затем `ollama list` |
| Документ долго в `Индексируется` | Смотрите `docker compose logs -f worker`; vision на CPU обрабатывается медленно |
| Ошибка памяти/503 | Закройте тяжёлые программы, `ollama stop <model>` или перейдите на `qwen3:4b` |
| Ответ пустой/некорректный | Проверьте `OLLAMA_THINK=false`, модель и источник; перезапустите новый диалог |
| После смены модели поиск стал хуже | Удалите и повторно загрузите документы: старые vectors несовместимы |
| Docker не видит Ollama, а localhost работает | Убедитесь, что `.env` содержит `host.docker.internal`, а Ollama перезапущен после `OLLAMA_HOST` |

Официальные справочники: [Ollama macOS](https://docs.ollama.com/macos),
[Ollama Windows](https://docs.ollama.com/windows), [Ollama API](https://docs.ollama.com/api/chat),
[Docker host networking](https://docs.docker.com/desktop/features/networking/networking-how-tos/).
