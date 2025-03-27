from typing import Any, AsyncGenerator
from common.agent import reasoning_step
from pydantic import BaseModel
import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)


class Colour(BaseModel):
    hex: str


class ColourPalette(BaseModel):
    id: str
    name: str
    colours: list[Colour]
    url: str
    imageUrl: str


async def get_random_palettes(n: int = 1) -> AsyncGenerator[Any, None]:
    """Get a random palette from ColourLovers.

    It is recommended to display the imageUrl in the UI
    for the user so that they can see the palette.

    Parameters:
        n: int = 1
            The number of palettes to return.
            Maximum is 10.


    """
    yield reasoning_step(
        event_type="INFO",
        message="Fetching palettes...",
        details={"number of palettes": n},
    )

    async with httpx.AsyncClient() as client:
        tasks = []
        for _ in range(n):
            tasks.append(
                client.get(
                    "https://www.colourlovers.com/api/palettes/random",
                    params={"format": "json"},
                    headers={"User-Agent": "OpenBB Example Copilot"},
                    timeout=30,
                )
            )
        responses = await asyncio.gather(*tasks)
        if all(response.status_code == 200 for response in responses):
            logger.info(
                f"Retrieved the following palettes: {[response.json() for response in responses]}"
            )
            response_str = "-- Palettes --\n"
            for response in responses:
                payload = response.json()[0]
                colours = [Colour(hex=f"#{colour}") for colour in payload["colors"]]
                palette = ColourPalette(
                    id=str(payload["id"]),
                    name=payload["title"],
                    colours=colours,
                    url=payload["url"],
                    imageUrl=payload["imageUrl"],
                )
                # Let's format the response that the LLM will see
                # as the result of the function call.
                response_str += f"name: {palette.name}\n"
                response_str += f"url: {palette.url}\n"
                response_str += f"imageUrl (use this to display the palette image): {palette.imageUrl}\n"
                response_str += f"colours: {[c.hex for c in palette.colours]}\n"
                response_str += "-----------------------------------\n"

            yield reasoning_step(
                event_type="INFO",
                message="Palettes fetched successfully.",
            )
            yield response_str
        else:
            yield reasoning_step(
                event_type="ERROR",
                message="Failed to fetch palettes.",
                details={"error": "Failed to fetch palettes."},
            )
            yield "Failed to fetch palettes."
