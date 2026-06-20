from fastapi import APIRouter
from pydantic import BaseModel

from ..providers import market, watchlist

router = APIRouter()


class CreateList(BaseModel):
    name: str


class RenameList(BaseModel):
    name: str


class AddItem(BaseModel):
    symbol: str


def _payload() -> dict:
    """All lists, each with live quotes. Quotes are fetched in one batch."""
    lists = watchlist.get_all()
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
def get_watchlists():
    return _payload()


@router.post("/watchlists")
def create_list(body: CreateList):
    watchlist.create(body.name)
    return _payload()


@router.delete("/watchlists/{name}")
def delete_list(name: str):
    watchlist.delete(name)
    return _payload()


@router.put("/watchlists/{name}")
def rename_list(name: str, body: RenameList):
    watchlist.rename(name, body.name)
    return _payload()


@router.post("/watchlists/{name}/items")
def add_item(name: str, body: AddItem):
    watchlist.add(name, body.symbol)
    return _payload()


@router.delete("/watchlists/{name}/items/{symbol:path}")
def remove_item(name: str, symbol: str):
    watchlist.remove(name, symbol)
    return _payload()
