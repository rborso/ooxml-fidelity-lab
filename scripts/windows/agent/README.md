# Windows oracle agent

Renders DOCX to PDF with Microsoft Word, from a file queue, inside the
interactive desktop session.

## Why it has to work this way

Word COM fails in a service or SSH session (`0x80080005`): there is no desktop.
So the agent is started by the `Startup` folder of the auto-logon user, not by a
scheduled task and not over SSH. SSH is for staging files and reading logs.

## Protocol

```
C:\work\in\<jobid>\document.docx        input
C:\work\out\<jobid>\document.pdf        output
C:\work\out\<jobid>\result.json         timing, word version, error
C:\work\out\<jobid>\DONE | FAIL         terminal marker
C:\work\STOP                            present  -> finish, do not shut down
C:\work\agent\agent.log                 append-only log
C:\work\agent\status.json               live state
```

The agent shuts the VM down when the queue has been empty for `IdleSeconds`.
Completion is then detected by the domain reaching `shut off` — no network
signal is needed, which is what allows the run to be fully offline.

## Files

| File | Role |
|---|---|
| `OracleAgent.ps1` | queue loop, watchdog, shutdown |
| `RenderOne.ps1` | one document, one fresh Word process, then exit |
| `start-oracle-agent.cmd` | Startup launcher |

## Watchdog

`RenderOne.ps1` runs in its own process so the parent can kill it. Word has no
cancellation: a hung document is a hung process. On timeout the child tree is
killed and any surviving `WINWORD.EXE` is force-stopped before the next job
starts, otherwise the failure leaks into the following document.

## Word settings

`UpdateFieldsBeforePrint` and `UpdateLinksAtOpen` are disabled — both make
output depend on the clock. Export uses `OptimizeFor=Print` (0), not on-screen,
so the PDF matches the printed layout.

## Deploy (offline, from the hypervisor)

```bash
# VM shut down, disk attached read-write with ntfs-3g
cp OracleAgent.ps1 RenderOne.ps1 /mnt/os/work/agent/
cp start-oracle-agent.cmd "/mnt/os/Users/linux/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/"
sync && umount /mnt/os
```

Then re-take the golden image; the agent is part of the image.

## Debug

Drop `C:\work\STOP` into the image before booting and the VM stays up after the
batch, so it can be inspected over the console.
