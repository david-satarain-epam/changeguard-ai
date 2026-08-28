from fastapi import FastAPI

app = FastAPI(title="ChangeGuard Dashboard")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
