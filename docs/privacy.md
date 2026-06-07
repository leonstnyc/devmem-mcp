# Privacy

DevMem is private by default.

## Stored Data

The SQLite database stores:

- note text and summaries
- note kind and tags
- related file paths
- tenant ID
- feedback ratings
- local or optional provider embeddings

The default path is `~/.devmem/devmem.db`.

## Network Use

The base install performs no telemetry and does not sync data remotely. OpenAI
embeddings are used only when the OpenAI extra is installed, `OPENAI_API_KEY` is
set, and `DEVMEM_FORCE_LOCAL_EMBEDDER` is not enabled.

## Delete Data

```bash
rm ~/.devmem/devmem.db
```

You can also set `DEVMEM_SQLITE_PATH` to use a project-specific database and
delete that file when needed.
