"""Fresh position/pen-axis IK derived directly from the loaded USD joint frames."""
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

JOINT_NAMES = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")


def quat_matrix(quat):
    """Isaac/USD uses wxyz; scipy accepts xyzw."""
    if hasattr(quat, "GetReal"):
        xyzw = [*quat.GetImaginary(), quat.GetReal()]
    else:
        xyzw = [*quat[1:], quat[0]]
    return Rotation.from_quat(xyzw).as_matrix()


def transform(position, quaternion):
    result = np.eye(4)
    result[:3, :3] = quat_matrix(quaternion)
    result[:3, 3] = position
    return result


class PenKinematics:
    def __init__(self, stage, root, tip_local):
        self.tip_local = np.asarray(tip_local, dtype=float)
        self.frames = []
        lower, upper = [], []
        for name in JOINT_NAMES:
            joint = stage.GetPrimAtPath(f"{root}/joints/{name}")
            if not joint.IsValid():
                raise RuntimeError(f"SO-101 joint is missing: {name}")
            get = lambda attr: joint.GetAttribute("physics:" + attr).Get()
            if get("axis") != "Z":
                raise RuntimeError(f"Unexpected joint axis on {name}")
            self.frames.append((transform(get("localPos0"), get("localRot0")),
                                np.linalg.inv(transform(get("localPos1"), get("localRot1")))))
            lower.append(np.radians(get("lowerLimit")))
            upper.append(np.radians(get("upperLimit")))
        self.lower = np.asarray(lower) + 0.01
        self.upper = np.asarray(upper) - 0.01

    def pose(self, joints):
        matrix = np.eye(4)
        for value, (parent, child_inverse) in zip(joints, self.frames):
            rotation = np.eye(4)
            rotation[:3, :3] = Rotation.from_rotvec([0, 0, value]).as_matrix()
            matrix = matrix @ parent @ rotation @ child_inverse
        return matrix[:3, :3] @ self.tip_local + matrix[:3, 3], matrix[:3, :3]

    def solve(self, target, seed):
        target = np.asarray(target, dtype=float)
        seed = np.clip(seed, self.lower, self.upper)

        def residual(joints):
            position, orientation = self.pose(joints)
            axis = orientation @ np.array([0.0, 0.0, -1.0])
            return np.r_[position - target, 0.045 * (axis - [0, 0, -1]), 0.01 * joints[4]]

        result = least_squares(residual, seed, bounds=(self.lower, self.upper),
                               ftol=1e-9, xtol=1e-9, gtol=1e-9, max_nfev=100)
        position, orientation = self.pose(result.x)
        error = float(np.linalg.norm(position - target))
        down = float((orientation @ np.array([0, 0, -1]))[2])
        if error > 0.0007 or down > -0.96:
            raise RuntimeError(f"Unreachable pen target {target.tolist()}: error={error:.4f}m, pen_down={down:.3f}")
        return result.x
