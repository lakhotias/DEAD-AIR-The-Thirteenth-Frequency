# DEAD AIR: The Thirteenth Frequency

A Pygame survival-puzzle maze built to match the Unit 3 Haunted Maze AI assignment and game design document. **The same `main.py` runs on desktop and in a browser via Pygbag.** You do not need to rewrite the game in JavaScript.

## Desktop game

Requires Python 3.11+.

```bash
python -m pip install -r requirements.txt
python main.py
```

## Test the browser version locally

```bash
python -m pip install pygbag
cd ..                         # parent of dead-air-game
python -m pygbag dead-air-game
```

Open `http://localhost:8000` in a browser. Click the canvas to focus it, then use the keyboard. For a build without a local server:

```bash
python -m pygbag --build dead-air-game
```

This produces `dead-air-game/build/web/` (including `index.html` and the bundled game). The browser initially downloads the Python/WASM runtime, so the first launch can be slower and requires internet connectivity.

## GitHub + Vercel: automatic browser publication

1. Upload this **entire folder's contents** to a new GitHub repository. Keep `.github/workflows/build-web.yml`, `main.py`, `public/`, and `vercel.json` at the repository root.
2. Use **main** as the default GitHub branch. In repository Settings > Actions > General, ensure workflows can run, and set Workflow permissions to **Read and write permissions** if your repository requires it. GitHub might ask you to approve the workflow.
3. On every push to `main` that changes source files, the included GitHub Action installs Pygbag, packages `main.py`, and commits the resulting static browser site into `public/`. Check the **Actions** tab and make sure it completed successfully.
4. In Vercel, **Add New Project**, import the GitHub repository, leave the root directory as repository root, and deploy. The included `vercel.json` uses no framework and serves the `public/` folder. The action's `public/` commit causes a new Vercel deployment, or redeploy manually after the Action completes.
5. Open the resulting `*.vercel.app` address. Click inside the game before using the keyboard.

**Important:** The initially included `public/index.html` is only a build-pending placeholder. It is replaced by the GitHub Action after Pygbag successfully builds the actual browser player. Merely uploading unbuilt Python files to Vercel is not sufficient. If Actions cannot push because of protected branches, build locally and copy the **contents** of `build/web/` into `public/`, commit those files, and push. Large generated files may exceed repository limits; an artifact-based deployment is an alternative.

## How to play

- **Enter** at the menu: begin; **M**: Probability Mixer; **H**: instructions.
- **WASD / arrow keys:** walk along open maze connections.
- **E:** spend a stored EMP charge and stun Hushlings within 2 graph steps for 2 seconds. The Listener is immune.
- **F1:** show/hide AI debug paths, FSM states, Markov probabilities and Boss candidate scoring.
- **P:** pause/resume. **Esc / Q:** return to the main menu while playing.
- **R** on a win/lose screen: restart with new maze, preserving probability sliders. **M:** menu; **Q:** quit.

Collect **5 Signal Shards**, then touch the transmitter at logical cell (14,14) to win. Pick up mint batteries to heal 20 HP, or store an EMP charge (max 3) when HP is already full. Avoid Feedback Puddles, Static Snares, Hushlings, and THE LISTENER. Score: 100 per shard, 500 for escape, plus 5 per remaining HP.

## Artificial intelligence, visible in F1

| Component | Method |
|---|---|
| Maze | Iterative depth-first recursive-backtracking maze generation, all 225 cells connected |
| Spawns | Four independent probability rolls, no object overlaps, at least 5 and at most 12 shards, safe starting zone |
| Navigation | Shared A* with Manhattan heuristic, priority queue, explicit reconstructed paths and explored-node count |
| Hushlings | FSM `PATROL -> CHASE -> SEARCH` plus `STUNNED`, line of sight, waypoint and search A* navigation |
| Player model | Online 4x4 first-order Markov matrix, smoothing pseudocounts of 1, updated on successful movements |
| **Advanced extension** | Second-order (2-gram) transition matrix, used by actual Boss decisions once a context has >=5 observed transitions; first-order fallback |
| Listener | Branch over up to 3 legal future steps using Markov probabilities, choose up to 5 ambush cells, evaluate `100*P - 4*BossDistance - 2*PlayerSteps` with a feasibility check, and A* to selected target |
| Metrics | F1 reveals candidate cells, scores, states, paths, movement counts, transition counts, rolling and lifetime prediction accuracy, and world seed |

Boss reevaluates every 0.75 s; Hushlings move at 0.35/0.55 s depending on FSM state. Boss speed is 0.48 s per cell. Note that predictions are probabilistic and not guaranteed to be accurate.

## Probability controls

| Category | Default | Range |
|---|---:|---:|
| Signal Shards | 4% | 2–10% |
| Recharge Cells | 6% | 0–15% |
| Feedback Puddles | 8% | 0–15% |
| Static Snares | 7% | 0–15% |

Select a slider using the Up/Down keys and change with Left/Right, or click the track. The shown spawn estimate assumes approximately 215 eligible cells and is intentionally approximate; reserved cells, caps, and the five-shard guarantee affect the actual count.

## Known limitations

- Art is deliberately drawn with Pygame shapes. No custom audio files have been added. The game is playable without sound.
- A desktop-sized 1280 x 800 canvas and physical keyboard are recommended. The browser build is not optimized for mobile touch controls.
- Pygbag needs to download a WebAssembly runtime on first launch, and availability/loading depends on the browser and its network.
- A 15x15 perfect maze has many dead ends, so interception candidates may be limited by local reachable directions.
- This package has syntax and algorithm tests, but a full graphical browser test and live Vercel deployment must be performed after upload.

## 60–90-second AI demonstration plan

1. Open the Probability Mixer and change one reward and one hazard setting. Start a new maze.
2. Press F1; explain DFS walls and the purple Hushling A* path / state transitions.
3. Walk through several turns and show the first-order prediction distribution. Repeat a two-turn pattern to accumulate 2-gram observations.
4. Point out the Boss's proposed cells, utility values, selected orange target and coral path. Explain why it is an interception rather than simply a direct chase.
5. Explain how to stun a Hushling with E, and the win condition.

## Troubleshooting

- If `python main.py` says `No module named pygame`, install `pygame-ce` with the same Python interpreter used to run it.
- If the Vercel page says `browser build pending`, check the GitHub Actions run and the latest commit to `public/index.html`.
- If GitHub Actions cannot push, check Action workflow permissions and branch protections.
- If the game has no keyboard response in the browser, click the game canvas first.
- If packaging fails, try `python -m pygbag --build dead-air-game` from its parent directory and examine the reported error.

References: [Pygbag documentation](https://pygame-web.github.io/wiki/pygbag/), [Vercel project configuration](https://vercel.com/docs/project-configuration).
