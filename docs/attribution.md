# Attribution and event contribution

Checked on 6 October 2026. This records provenance; it does not relicense
third-party software or assets.

## Application code

`backend/` implements the model request, validation, previews and job API.
`sim/` contains the scene setup, inverse kinematics, drawing worker and measured
pen-path recording. `frontend/` contains the browser implementation. Tests,
scripts and documentation support deployment with each operator's own resources.

Codex assisted development. Astra generates stroke plans at runtime. The Lovable
integration prompts are in this repository; a separately created Lovable project
has its own generated source and deployment.

## Existing components and assets

| Component | Provenance and treatment |
| --- | --- |
| Isaac Sim / Omniverse / PhysX | NVIDIA simulator and runtime, installed separately; not authored here or redistributed in this repository. |
| SO-101 robot geometry and articulation | RobotStudio asset from NVIDIA's versioned Isaac Sim 5.1 collection, downloaded by `sim/fetch_assets.py`; `sim/assets/` is excluded from Git. |
| Python and browser libraries | Third-party dependencies declared in `backend/requirements.txt`, `requirements.lock.txt`, and `frontend/package-lock.json`; their own licenses apply. |

The robot download consists of `so101_new_calib.usd` and the `base`, `physics`,
`robot` and `sensor` configuration USD layers, under this
[exact NVIDIA 5.1 source directory](https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Robots/RobotStudio/so101_new_calib/so101_new_calib.usd).
The [Isaac Sim 5.1 robot catalog](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/assets/usd_assets_robots.html#usd-path-robotstudio-so101-new-calib-so101-new-calib-usd)
lists that asset. No asset-specific license text was found in the five
downloaded layers' `customLayerData` or layer comments; both fields are empty.
The fetch script does not fetch a license file.

NVIDIA's [5.1 licensing page](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/common/licenses-isaac-sim.html)
distinguishes its Apache-2.0 source from additional components, including models
and textures, and points to the
[Additional Software and Materials License](https://www.nvidia.com/en-us/agreements/enterprise-software/isaac-sim-additional-software-and-materials-license/).
The installed `PACKAGE-LICENSES/isaac-sim-assets-LICENSE.txt` also directs users
to asset-folder notices. NVIDIA's
[current manipulator catalog](https://docs.isaacsim.omniverse.nvidia.com/latest/assets/usd_assets_robots_manipulator.html#robotstudio)
labels SO-101 Apache 2.0 and links to TheRobotStudio, whose
[repository license](https://github.com/TheRobotStudio/SO-ARM100/blob/main/LICENSE)
is Apache 2.0. The 5.1 catalog does not state that per-asset license, so this
is supporting provenance rather than confirmation of the exact downloaded
5.1 files' license. Those asset files remain excluded from the public source.

Use portrait inputs you have permission to process and show.
No private input photos, secrets, downloaded simulator assets, or installed
dependency trees are included in the repository. The arm asset and NVIDIA's
simulation/rendering capabilities are existing components; this project adds the
application and controller around them.
