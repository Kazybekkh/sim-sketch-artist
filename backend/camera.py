"""Finite, bounded camera poses accepted from the browser."""
import math
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class CameraPose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yaw: Number = Field(ge=-2 * math.pi, le=2 * math.pi)
    pitch: Number = Field(ge=0.10, le=1.55)
    distance: Number = Field(ge=0.12, le=1.5)
    target: list[Number] = Field(min_length=3, max_length=3)

    @field_validator("target")
    @classmethod
    def target_in_scene(cls, target):
        if not (-0.5 <= target[0] <= 0.5 and -0.5 <= target[1] <= 0.5 and 0 <= target[2] <= 0.5):
            raise ValueError("Camera target must remain inside the drawing scene.")
        return target

    @classmethod
    def from_simulator(cls, camera):
        # USD uses float transforms. A valid boundary pose can read back a few
        # nanometers outside its requested bounds; never disable reset for that.
        def measured(value, lower, upper):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Invalid simulator camera number")
            if not lower - 1e-6 <= value <= upper + 1e-6:
                raise ValueError("Simulator camera is outside the scene")
            return max(lower, min(upper, value))

        target = camera["target"]
        if not isinstance(target, list) or len(target) != 3:
            raise ValueError("Invalid simulator camera target")
        return cls(yaw=measured(camera["yaw"], -2 * math.pi, 2 * math.pi),
                   pitch=measured(camera["pitch"], 0.1, 1.55),
                   distance=measured(camera["distance"], 0.12, 1.5),
                   target=[measured(target[0], -0.5, 0.5), measured(target[1], -0.5, 0.5),
                           measured(target[2], 0, 0.5)])
