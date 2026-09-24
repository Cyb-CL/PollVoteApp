from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
from fastapi.middleware.cors import CORSMiddleware
import os
import jwt

# Connection to MongoDB(polldb)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["polldb"]
polls_collection = db["polls"]

#Configuration of the JWT secret, shared with auth and vote service
JWT_SECRET = os.environ.get("JWT_SECRET", "secretkey-pollvoteapp")
JWT_ALGORITHM = "HS256"

#Initialization of FastApi with CORS abilities 
app = FastAPI(title="Poll Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

#FastApi extracts the token Bearer JWT and validates it from the header authorization 
def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

class PollCreate(BaseModel):
    question: str
    options: list[str]

def poll_helper(poll) -> dict:
    return {
        "id": str(poll["_id"]),
        "question": poll["question"],
        "options": poll["options"],
        "created_by": poll.get("created_by", "anonymous"),
        "voted_by": poll.get("voted_by", [])
    }

# ENDPOINT
@app.post("/polls")
def create_poll(poll: PollCreate, current_user: str = Depends(get_current_user)):
    if len(poll.options) < 2:
        raise HTTPException(status_code=400, detail="A poll needs at least 2 options")

    poll_doc = {
        "question": poll.question,
        "options": [{"text": opt, "votes": 0} for opt in poll.options],
        "created_by": current_user,
        "voted_by": [],
    }

    result = polls_collection.insert_one(poll_doc)
    created_poll = polls_collection.find_one({"_id": result.inserted_id})
    return poll_helper(created_poll)

#Pollslist
@app.get("/polls")
def list_polls():
    polls = polls_collection.find()
    return [poll_helper(p) for p in polls]

#GetPolls by their id
@app.get("/polls/{poll_id}")
def get_poll(poll_id: str):
    try:
        obj_id = ObjectId(poll_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid poll ID format")

    poll = polls_collection.find_one({"_id": obj_id})
    if poll is None:
        raise HTTPException(status_code=404, detail="Poll not found")

    return poll_helper(poll)
