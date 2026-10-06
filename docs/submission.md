# Sim Sketch Artist — submission draft

For the GPT-6 Astra Hackathon London, 6 October 2026. Submission deadline:
**20:30 Europe/London**. This is a draft; it has not been submitted.

| Field | Value |
| --- | --- |
| Project | Sim Sketch Artist |
| Team name | **Missing — confirm** |
| All team members | **Missing — confirm names, maximum four people** |
| Public repository | [Kazybekkh/sim-sketch-artist](https://github.com/Kazybekkh/sim-sketch-artist) |
| Published app | [Sim Sketch Artist](https://sim-sketch-artist.lovable.app/) |
| One-minute public demo with screen and audio | **Missing — record, publish and add the URL** |

## Project description

Sim Sketch Artist connects a portrait in a Lovable browser app to a drawing
robot in NVIDIA Isaac Sim. Capture a photo or upload an image; GPT-6 Astra
turns the image into a compact set of pen strokes. Our backend validates and
orders the strokes, and our controller moves a simulated SO-101 arm through
them. The finished drawing is rendered from the arm's measured pen-tip path.
This makes the connection between visual AI and robot motion visible and
testable without a physical robot.

## What we built and how we used the tools

The event contribution is the portrait-to-strokes prompt and API integration,
validation and preview pipeline, file-based job queue, SO-101 drawing
controller and measured trail, browser workflow, and integration with the
Lovable app. The source was first committed on 6 October at 19:18 BST; the
repository history and [verification notes](verification.md) document this
build. Existing libraries, Isaac Sim, and the downloaded SO-101 robot asset
are dependencies, not claimed as event inventions. See [attribution](attribution.md).

Lovable was used to create and publish the user-facing app. Codex assisted
implementation, debugging and verification. At runtime GPT-6 Astra receives
the portrait and returns bounded stroke coordinates through the OpenAI API.
The model does not generate or execute robot-control code. Do not claim a
specific development-model identity without a supporting build record.

| Judging criterion | Concrete evidence to show |
| --- | --- |
| Astra and Lovable in development — 25% | Lovable project history; event commits; explain the prompt, validation and simulator integration work. |
| Astra and Lovable in the project — 25% | A fresh image produces a fresh Astra stroke preview in the published app, followed by a robot job. |
| Demo video — 25% | One clear 60-second story: image → Astra preview → actual Isaac Sim arm drawing → measured result, with narration. |
| Technical execution — 25% | Show the arm moving, job progress and finished trace; point to bounded inputs, atomic queue writes and documented tests. |

## Exactly 60-second video plan

Record a complete working run first, with screen capture and microphone audio.
Then edit to the timing below; allow short pauses to fill each narration slot.
Show a webcam capture if available, or upload the synthetic test portrait and
label it **Synthetic test portrait**. The supplied rules do not require webcam
footage. If shortening API waiting time, label the cut **Wait shortened**.
Never substitute a prerecorded robot clip while presenting it as the current job.

The reference browser studio now includes the live Isaac view; a new 13-stroke
job produced 44 distinct frames over HTTPS and completed successfully. Use
that view for the arm shot. The separate Lovable deployment can embed the
same feed using [these instructions](lovable-live-view.md). The following is
a recording script, not a claim that the final video already exists.

| Time | Screen shot | Exact narration |
| --- | --- | --- |
| 00:00–00:07 | Published Lovable app, project name and input area. | “This is Sim Sketch Artist: a portrait becomes a drawing made by a simulated robot arm.” |
| 00:07–00:16 | Capture a photo or upload the labeled synthetic portrait; click Sketch me. | “I start with a picture in our Lovable app. Astra reads the image and plans a simple line portrait.” |
| 00:16–00:27 | Fresh Astra preview, then job progress. Label any shortened waiting time. | “We validate its stroke coordinates and send them to our drawing controller. The model supplies the sketch; our code turns those strokes into joint motion.” |
| 00:27–00:44 | Make the actual Isaac Sim arm the largest view; retain current job progress. Show pen travel, pen-down drawing and new marks. | “Here is the SO-101 actually moving in Isaac Sim. Its gripper carries the pen across the virtual page. We record the measured pen-tip path, so the result reflects what the simulated arm traced.” |
| 00:44–00:52 | Finished trace beside source image and Astra preview. | “Here is the finished drawing. This is simulation: gravity is disabled and the ink is geometric.” |
| 00:52–01:00 | Brief event source overview, then readable public repository and app URLs. | “Built during this hackathon with Lovable and Codex, using Astra at runtime. Our code and verification are public.” |

Keep a readable **Isaac Sim — simulated SO-101** label on the arm footage.
The project does not control physical hardware, simulate pencil pressure or
paper contact forces, or implement an Astra critique-and-redraw loop.

## Remaining submission work

- Fill in the team name and every team member.
- Record and publish the 60-second screen-and-audio demo; open its URL while
  signed out to verify access. The existing 36.375-second viewport recording
  demonstrates the arm only and does not cover this full requirement.
- Push the final event code and documentation; open the public repository
  while signed out. Identify the exact submitted Lovable source or project
  history alongside the reference frontend where available.
- Check the app and demo links, insert the final video URL above, and submit
  through the event's London submission page before 20:30.

The published app depends on the Ubuntu backend, tunnel and Isaac worker
remaining running. Current tested scope and remaining webcam-specific checks
are recorded in [verification.md](verification.md).
