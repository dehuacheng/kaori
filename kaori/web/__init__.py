from fastapi.templating import Jinja2Templates

from kaori.config import BASE_DIR, TEST_MODE

templates = Jinja2Templates(directory=str(BASE_DIR / "kaori" / "templates"))
templates.env.globals["test_mode"] = TEST_MODE
