from textual.app import App, ComposeResult
from textual.containers import Container, Content, Horizontal
from textual.widgets import Header, Footer, Static, Input, TextLog, Button, Switch, Label, Placeholder

class LeftColumn(Static):
    def compose(self) -> ComposeResult:
        yield Label("Power")
        yield Switch()
        yield Placeholder("placeholder")

class CenterColumn(Static):
    def compose(self) -> ComposeResult:
        yield Label("Colors")
        yield Button("Warm White")
        yield Button("Blue")
        yield Button("Red")
        yield Button("Purple")
        yield Button("Violet")
        yield Button("Green")
        yield Button("Light Blue")

class RightColumn(Static):
    def compose(self) -> ComposeResult:
        yield Label("custom color:")
        yield Input(placeholder="Enter a hex color code")

class LightApp(App):
    CSS_PATH = "gui.css"
    """A Textual app to manage a light."""
    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        yield Container(LeftColumn(), id="left-column")
        yield Container(CenterColumn(), id="center-column")
        yield Container(RightColumn(), id="right-column")

        with Content(id="logs-container"):
            yield TextLog(id="textlog")

    def on_mount(self) -> None:
        """Called when app starts."""
        # Give the input focus, so we can start typing straight away
        # self.query_one(Input).focus()
        ...


if __name__ == "__main__":
    app = LightApp()
    app.run()
