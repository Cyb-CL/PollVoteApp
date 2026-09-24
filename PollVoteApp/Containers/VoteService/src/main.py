
from fastapi import FastAPI, HTTPException, Header, Depends
from pymongo import MongoClient
from pydantic import BaseModel
from bson import ObjectId
from fastapi.middleware.cors import CORSMiddleware
import os
import jwt

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["polldb"]
polls_collection = db["polls"]

JWT_SECRET = os.environ.get("JWT_SECRET", "secretkey-pollvoteapp")
JWT_ALGORITHM = "HS256"

app = FastAPI(title="Vote Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

class VoteUpdate(BaseModel):
    option: str

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

def poll_helper(poll) -> dict:
    return {
        "id": str(poll["_id"]),
        "question": poll["question"],
        "options": poll["options"],
        "created_by": poll.get("created_by", "anonymous"),
        "voted_by": poll.get("voted_by", [])
    }

# Registration of the polls vote, only one vote per poll can be added by the same user
@app.post("/polls/{poll_id}/vote")
def vote_poll(poll_id: str, vote: VoteUpdate, current_user: str = Depends(get_current_user)):
    # Validazione ObjectId MongoDB
    try:
        obj_id = ObjectId(poll_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid poll ID format")

    existing_poll = polls_collection.find_one({"_id": obj_id})
    if existing_poll is None:
        raise HTTPException(status_code=404, detail="Poll not found")

    if current_user in existing_poll.get("voted_by", []):
        raise HTTPException(status_code=400, detail="You have already voted on this poll")

    # Check to see if the voted_by doesn't contain the current_user
    #  increments the count and adds the suer 

    result = polls_collection.update_one(
        {"_id": obj_id, "options.text": vote.option, "voted_by": {"$ne": current_user}},
        {
            "$inc": {"options.$.votes": 1},
            "$push": {"voted_by": current_user}
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=400, detail="Poll option not found or you have already voted")

    updated_poll = polls_collection.find_one({"_id": obj_id})
    return poll_helper(updated_poll)