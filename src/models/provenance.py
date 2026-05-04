
from pydantic import BaseModel

class Bbox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
