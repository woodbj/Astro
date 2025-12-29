"""
Interactive Python terminal backend for Flask.
Provides a REPL that can be accessed via websockets.
"""
import sys
import io
import code
import traceback
from contextlib import redirect_stdout, redirect_stderr


class InteractiveConsole:
    """A Python REPL that captures output and can be used via websockets."""

    def __init__(self, locals=None):
        """
        Initialize the interactive console.

        Args:
            locals: Dictionary of local variables to make available in the REPL
        """
        self.locals = locals or {}
        self.console = code.InteractiveConsole(self.locals)
        self.output_buffer = io.StringIO()

    def execute(self, source):
        """
        Execute Python code and capture output.

        Args:
            source: Python code to execute

        Returns:
            Dictionary with output and error information
        """
        self.output_buffer = io.StringIO()
        error = None

        try:
            # Redirect stdout and stderr to capture output
            with redirect_stdout(self.output_buffer), redirect_stderr(self.output_buffer):
                # Try to compile and execute the code
                try:
                    compiled = code.compile_command(source, '<console>', 'single')
                    if compiled is None:
                        # Incomplete input
                        return {
                            'output': '',
                            'error': None,
                            'incomplete': True
                        }

                    # Execute the compiled code
                    exec(compiled, self.locals)

                except SyntaxError as e:
                    # Syntax error - format it nicely
                    traceback.print_exception(type(e), e, e.__traceback__)
                    error = str(e)

                except Exception as e:
                    # Runtime error - format it nicely
                    traceback.print_exception(type(e), e, e.__traceback__)
                    error = str(e)

        except Exception as e:
            # Catch any errors in the redirect context
            error = f"Internal error: {str(e)}"

        output = self.output_buffer.getvalue()

        return {
            'output': output,
            'error': error,
            'incomplete': False
        }

    def get_locals(self):
        """Get the current local variables."""
        return self.locals

    def reset(self):
        """Reset the console state."""
        self.console.resetbuffer()
        self.output_buffer = io.StringIO()
