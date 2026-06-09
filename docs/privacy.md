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

The database runs in WAL mode, so note data can also live in the `-wal` and
`-shm` sidecar files next to the database. Delete all three:

```bash
rm -f ~/.devmem/devmem.db ~/.devmem/devmem.db-wal ~/.devmem/devmem.db-shm
```

You can also set `DEVMEM_SQLITE_PATH` to use a project-specific database and
delete those files when needed.
