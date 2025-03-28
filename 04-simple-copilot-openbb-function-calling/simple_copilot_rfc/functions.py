from typing import AsyncGenerator, Callable
from common.agent import reasoning_step, get_remote_data, remote_function_call
from common.models import (
    DataContent,
    FunctionCallSSE,
    StatusUpdateSSE,
    WidgetCollection,
)


async def handle_widget_data(data: list[DataContent]) -> str:
    result_str = "--- Data ---\n"
    for content in data:
        result_str += f"{content.content}\n"
        result_str += "------\n"
    return result_str


def get_widget_data(widget_collection: WidgetCollection) -> Callable:
    # This function returns a callable, so that we can pass in the `widgets`
    # argument when the function is defined, and not when it is called by the
    # LLM (since we only want the LLM to specify the widget UUID of the widget
    # that it wants data for).
    widgets = (
        widget_collection.primary + widget_collection.secondary
        if widget_collection
        else []
    )

    @remote_function_call(
        function="get_widget_data", output_formatter=handle_widget_data
    )
    async def _get_widget_data(
        widget_uuid: str,
    ) -> AsyncGenerator[FunctionCallSSE | StatusUpdateSSE, None]:
        """Retrieve data for a widget by specifying the widget UUID."""

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
            input_arguments={
                param.name: param.current_value for param in widget.params
            },
        )

    return _get_widget_data
