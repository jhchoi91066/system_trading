from fastapi import FastAPI
from db import supabase

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/users")
async def get_users():
    response = supabase.table("users").select("*").execute()
    return response.data