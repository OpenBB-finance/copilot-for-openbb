import random
from typing import AsyncGenerator
from common.agent import reasoning_step, get_remote_data, remote_function_call
from common.callbacks import cite_widget
from common.models import (
    QueryRequest,
    DataContent,
    FunctionCallSSE,
    StatusUpdateSSE,
)
import httpx
from pydantic import BaseModel


class Rating(BaseModel):
    average: float
    reviews: int


class Beer(BaseModel):
    id: int
    price: str
    name: str
    rating: Rating
    image: str


async def get_random_stout_beers(n: int = 1) -> AsyncGenerator[str, None]:
    """Get a random stout beer from the Beer API.

    It is recommended to display the image url in the UI
    for the user so that they can see the beer.

    Parameters:
        n: int = 1
            The number of beers to return.
            Maximum is 10.


    """
    yield reasoning_step(
        event_type="INFO",
        message="Fetching random stout beers...",
        details={"number of beers": n},
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.sampleapis.com/beers/stouts",
            headers={"User-Agent": "OpenBB Example Copilot"},
        )
        if response.status_code != 200:
            yield reasoning_step(
                event_type="ERROR",
                message="Failed to fetch beers.",
                details={"error": "Failed to fetch beers."},
            )
            yield "Failed to fetch beers."
            return

        yield reasoning_step(
            event_type="INFO",
            message="Beers fetched successfully.",
        )

        data = response.json()
        random_sample = random.sample(data, n)
        beers = [Beer(**beer) for beer in random_sample]

        response_str = "-- Beers --\n"
        for beer in beers:
            response_str += f"name: {beer.name}\n"
            response_str += f"price: {beer.price}\n"
            response_str += f"rating: {beer.rating.average}\n"
            response_str += f"reviews: {beer.rating.reviews}\n"
            response_str += (
                f"image (use this to display the beer image): {beer.image}\n"
            )
            response_str += "-----------------------------------\n"
        yield response_str
        return


async def handle_widget_data(data: list[DataContent]) -> str:
    result_str = "--- Data ---\n"
    for result in data:
        for item in result.items:
            result_str += f"{item.content}\n"
            result_str += "------\n"
    return result_str


# We will use a built-in callback which will automatically yield citations for
# any widget who's data is retrieved.
@remote_function_call(
    function="get_widget_data",
    output_formatter=handle_widget_data,
    callbacks=[
        cite_widget,
    ],
)
async def get_widget_data(
    widget_uuid: str, request: QueryRequest
) -> AsyncGenerator[FunctionCallSSE | StatusUpdateSSE, None]:
    """Retrieve data for a widget by specifying the widget UUID."""

    widgets = (
        request.widgets.primary + request.widgets.secondary if request.widgets else []
    )

    # Get the first widget that matches the UUID (there should be only one).
    matching_widgets = list(
        filter(lambda widget: str(widget.uuid) == widget_uuid, widgets)
    )
    widget = matching_widgets[0] if matching_widgets else None

    # If we're unable to find the widget, let's the the user know.
    if not widget:
        yield reasoning_step(
            event_type="ERROR",
            message="Unable to retrieve data for widget (does not exist)",
            details={"widget_uuid": widget_uuid},
        )
        # And let's also return a message to the LLM.
        yield f"Unable to retrieve data for widget with UUID: {widget_uuid} (it is not present on the dashboard)"  # noqa: E501
        return

    # Let's let the user know that we're retrieving data for the widget.
    yield reasoning_step(
        event_type="INFO",
        message=f"Retrieving data for widget: {widget.name}...",
        details={"widget_uuid": widget_uuid},
    )

    # And now let's make the request to the front-end for the widget data.
    # NB: You *must* yield using `agent.remote_data_request` from inside
    # remote functions (i.e. those decorated with `@remote_function`).
    yield get_remote_data(
        widget=widget,
        # In this example we will just re-use the currently-set values of
        # the widget parameters.
        input_arguments={param.name: param.current_value for param in widget.params},
    )
