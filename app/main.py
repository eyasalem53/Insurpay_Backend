from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.session import engine
from app.database.models import Base
from app.auth.routes import router as auth_router
from app.users.routes import router as users_router
from app.agent.router import router as agent_router
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="InsurPay Analytics Platform API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(agent_router)
app.include_router(auth_router)
app.include_router(users_router)

@app.get("/")
def root():
    return {
        "message": "InsurPay Analytics Platform API is running"
    }