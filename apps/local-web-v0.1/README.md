# MonoGrowLab local workbench 0.1

## Open

Double-click `start.cmd` in this folder. It uses the existing Python 3.13 environment and opens `http://127.0.0.1:8767/`. Keep the console open while a task is running. Closing a browser tab does not cancel the task. No Windows service, startup task, firewall exception or new Python dependency is installed.

中文：双击 `start.cmd` 打开网页。第一次可以选 validation 的前两张图、96 px、CLERG 和 Gaussian noise，点 Start evaluation。界面有英文标签与参数说明；运行后可看图、指标及 HTML 报告。浏览器关掉不影响任务，但请保留启动窗口。新任务全部保存在项目 `ui_runs/`，与论文数据隔离。

## Evaluate

1. Select the existing BSDS500 training or validation split and 2–20 image IDs.
2. Select growth variants and Gaussian-smoothed or raw strict-extrema seed policy.
3. Select corruption families and severities, then start a run. Random families use the selected replicate count; deterministic families use one realization.
4. Follow execution, analysis and report stages. Open the report or download exact configuration and CSV outputs.
5. The illustrative preview reconstructs the first image/variant/corruption condition. Its corrupted-pixel hash and quality/stability metrics must match the saved run before it is displayed. Boundary overlays are displayed on the same corrupted image; they are not manually drawn or historical benchmark screenshots.

The page reports image count, the number of variants in each Holm correction family, and the minimum attainable raw sign-flip p value. A two-image run has minimum p=0.5: it checks the workflow, not statistical significance. Interactive results are exploratory, not an automatic reproduction of the manuscript's frozen verdict. Changing the selected variants changes the correction family.

## Scope

This version uses the existing BSDS500 adapter and local dataset; arbitrary image uploads and other dataset formats are not implemented. The held-out test split cannot be launched from the UI. Existing manuscript HTML reports are read-only links. No cancellation/deletion control is exposed; partial files survive failures. After an interrupted server session, tasks are not resumed automatically. If a prior recorded subprocess is still alive, new runs are refused until it exits.

The workbench executes the same v2 scripts used by the CLI, without editing them. Job configuration and output paths are generated inside `ui_runs/<unique-id>/`. Algorithms, frozen configurations and paper experiments remain unchanged. The server listens only on loopback and is not intended for public hosting. Writes require a per-launch token and permitted Host/Origin; files are served from constrained paths. Do not proxy it onto the internet.

## Test

From this folder, run `py -3.13 -m unittest test_server -v`. Test fixtures are retained in `%TEMP%\MonoGrowLab\web-tests\` for inspection; there is no automatic deletion.


