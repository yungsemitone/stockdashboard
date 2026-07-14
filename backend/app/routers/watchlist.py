from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..providers import market, watchlist
from . import auth

router = APIRouter()


class CreateList(BaseModel):
    name: str


class RenameList(BaseModel):
    name: str


class AddItem(BaseModel):
    symbol: str


def _payload(lists: list[dict]) -> dict:
    """The given lists, each with live quotes fetched in one batch."""
    all_symbols = sorted({s for l in lists for s in l["symbols"]})
    quotes = {q["symbol"]: q for q in market.quotes_for(all_symbols)}
    return {
        "lists": [
            {
                "name": l["name"],
                "symbols": l["symbols"],
                "quotes": [quotes[s] for s in l["symbols"] if s in quotes],
            }
            for l in lists
        ]
    }


@router.get("/watchlists")
def get_watchlists(request: Request):
    # Sessions get their own lists; the service token (Morning Desk) reads as
    # the primary account — or the legacy pool until any account exists.
    try:
        user = auth.current_account(request)
        return _payload(watchlist.get_all(user["id"]))
    except HTTPException:
        if auth.is_service(request) or not auth.settings.dashboard_password:
            return _payload(watchlist.get_all(None))
        raise


@router.post("/watchlists")
def create_list(body: CreateList, request: Request):
    user = auth.require_account(request)
    return _payload(watchlist.create(user["id"], body.name))


@router.delete("/watchlists/{name}")
def delete_list(name: str, request: Request):
    user = auth.require_account(request)
    return _payload(watchlist.delete(user["id"], name))


@router.put("/watchlists/{name}")
def rename_list(name: str, body: RenameList, request: Request):
    user = auth.require_account(request)
    return _payload(watchlist.rename(user["id"], name, body.name))


@router.post("/watchlists/{name}/items")
def add_item(name: str, body: AddItem, request: Request):
    user = auth.require_account(request)
    return _payload(watchlist.add(user["id"], name, body.symbol))


@router.delete("/watchlists/{name}/items/{symbol:path}")
def remove_item(name: str, symbol: str, request: Request):
    user = auth.require_account(request)
    return _payload(watchlist.remove(user["id"], name, symbol))
