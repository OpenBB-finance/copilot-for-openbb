import sys
import io
from code import InteractiveConsole
from multiprocessing import Queue
from typing import Any


class CapturingInteractiveConsole(InteractiveConsole):
    def __init__(self, locals=None):
        super().__init__(locals=locals)
        self.output_buffer = io.StringIO()

    def runcode(self, code):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = self.output_buffer
        sys.stderr = self.output_buffer

        try:
            super().runcode(code)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def get_output(self):
        val = self.output_buffer.getvalue()
        self.output_buffer.seek(0)
        self.output_buffer.truncate(0)
        return val.rstrip("\n")


def repl_worker(input_queue: Queue, output_queue: Queue, local_context: dict[str, Any]):
    console = CapturingInteractiveConsole(locals=local_context)
    # Load our utility functions that the LLM can use to return structured data
    console.runcode(
        "import numpy as np\n"
        "import pandas as pd\n"
        "import json\n"
        "\n"
        "def return_structured(data):\n"
        "    table_data = {\n"
        '        "type": "table",\n'
        "    }\n"
        "    if isinstance(data, pd.DataFrame):\n"
        '        table_data["content"] = data.to_json(orient="records", date_format="iso")\n'
        "    elif isinstance(data, pd.Series):\n"
        '        table_data["content"] = data.to_json(orient="records", date_format="iso")\n'
        "    elif isinstance(data, np.ndarray):\n"
        "        df = pd.DataFrame(data)\n"
        '        table_data["content"] = df.to_json(orient="records", date_format="iso")\n'
        "    return '```json\\n' + json.dumps(table_data) + '\\n```'\n"
        "\n"
        "def return_chart(df, chart_type, xKey, yKey):\n"
        "    chart_data = {\n"
        '        "type": "chart",\n'
        '        "content": df.to_json(orient="records", date_format="iso"),\n'
        '        "chart_params": {\n'
        '            "chartType": chart_type,\n'
        '            "xKey": xKey,\n'
        '            "yKey": yKey\n'
        "        }\n"
        "    }\n"
        "    return '```json\\n' + json.dumps(chart_data) + '\\n```'\n"
    )
    # Begin the REPL loop
    while True:
        code = input_queue.get()
        if code is None:
            break
        try:
            lines = code.strip().split("\n")
            if len(lines) > 1:
                # Execute all but the last line as statements
                stmt_code = "\n".join(lines[:-1])
                if stmt_code:
                    compiled_stmt = compile(stmt_code, "<input>", "exec")
                    console.runcode(compiled_stmt)

                # Try to evaluate the last line for its result
                try:
                    compiled_expr = compile(lines[-1], "<input>", "eval")
                    result = eval(compiled_expr, console.locals)
                    if result is not None:
                        print(result, file=console.output_buffer)
                except SyntaxError:
                    compiled_stmt = compile(lines[-1], "<input>", "exec")
                    console.runcode(compiled_stmt)
            else:
                # Single line - try as statement first, then expression
                try:
                    # Not pretty, but a quick way to handle the rare case where
                    # we get a print statement as a single line (since it can
                    # also get evaluated as an expression)
                    if "print(" in code:
                        compiled_stmt = compile(code, "<input>", "exec")
                        console.runcode(compiled_stmt)
                    else:
                        compiled_expr = compile(code, "<input>", "eval")
                        result = eval(compiled_expr, console.locals)
                        if result is not None:
                            print(result, file=console.output_buffer)
                except SyntaxError:
                    # If it's not a valid statement, try as expression
                    compiled = compile(code, "<input>", "eval")
                    result = eval(compiled, console.locals)
                    if result is not None:
                        print(result, file=console.output_buffer)

            output = console.get_output()
            output_queue.put(output)
        except Exception as e:
            output_queue.put(str(e))
