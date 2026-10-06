# Attribution and event contribution

Checked on 6 October 2026. This records provenance; it does not relicense
third-party software or assets.

## New work for this event

This isolated repository contains the application built for the hackathon:
`backend/` implements the Astra request, validation, previews and job API;
`sim/` contains our scene setup, inverse kinematics, drawing worker and
measured-path recording; `frontend/` is our reference browser implementation;
`samples/`, `tests/`, `scripts/` and project documentation support that workflow.
The initial source commit is `1baebe7`, dated 6 October 2026 at 19:18 BST.

The [Lovable project](https://lovable.dev/projects/23eb3da7-7b3a-499d-a095-c1112a6b197e)
is the separately created and published user-facing app. Its generated source
is not currently represented by `frontend/`, which is a reference implementation.
Codex assisted the event development. Astra generates stroke plans at runtime.

## Existing components and assets

| Component | Provenance and treatment |
| --- | --- |
| Isaac Sim / Omniverse / PhysX | NVIDIA simulator and runtime, installed separately; not authored here or redistributed in this repository. |
| SO-101 robot geometry and articulation | RobotStudio asset from NVIDIA's versioned Isaac Sim 5.1 collection, downloaded by `sim/fetch_assets.py`; `sim/assets/` is excluded from Git. |
| Python and browser libraries | Third-party dependencies declared in `backend/requirements.txt`, `requirements.lock.txt`, and `frontend/package-lock.json`; their own licenses apply. |
| Portrait test media and screenshots | The existing demo uses the documented synthetic test portrait. Screenshots and viewport recording are outputs of this project's simulation, including the third-party robot model. They do not show a verified Mac webcam session. |

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

Only use portrait inputs the demonstrator has permission to process and show.
No private input photos, secrets, downloaded simulator assets, or installed
dependency trees are included in the repository. The arm asset and NVIDIA's
simulation/rendering capabilities must be credited as existing components in
the submission; the new contribution is the application and controller around them.
