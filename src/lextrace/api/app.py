from fastapi import FastAPI

from lextrace.api.routes import router

app = FastAPI(title="LexTrace API")
app.include_router(router)
