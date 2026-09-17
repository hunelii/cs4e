# Before the workshop

Do this **before day 1**, on the laptop you are bringing.

You do **not** need to install Python, and you should not try — the tool in step 3 fetches its own Python version.

The workshop repository is **private**. You can only clone it once your GitHub username has been added to it, which is what step 1 is for. **Do step 1 as soon as possible.**

Every step ends with a check. If the check prints what it says it should, move on. If it does not, jump to [When something goes wrong](#when-something-goes-wrong).

---

## First: the terminal

Most steps below ask you to open **the terminal** and run a command. The terminal is a window where you type commands instead of clicking. Windows and Mac have one; only the name differs.

- **Windows** — press the Windows key, type `PowerShell`, press Enter.
- **macOS** — press `Cmd` + `Space`, type `Terminal`, press Enter.

From here on, "the terminal" means that window. To run a command, type it or paste it in, then press Enter. Commands are shown in boxes like this one:

```
git --version
```

> **After installing anything, close the terminal and open a fresh one.** A terminal that was already open cannot see a tool that was installed after it started.

---

## Step 1 — A GitHub account

GitHub is where the workshop code lives, and where your own work will end up on day 1.

If you do not have an account, create one at [github.com/signup](https://github.com/signup).

Then **send your GitHub username to your facilitator**. You will get an invitation email from GitHub. **Open it and accept it.** Until you do, step 5 won't be feasible. I'd advise you to go on with step two as soon as you got the email and then finish the setup in one go.

### Check

Sign in at [github.com](https://github.com) and confirm the username in the top-right menu is the one you sent to your facilitator.

---

## Step 2 — Git

Git is how you will save your work, undo mistakes, and hand code to somebody else.

**Windows** — download and run the installer and accept every default. It is a long wizard and none of it needs your attention. If you have an older device, x64 is the right one for you. If you have a new one with an ARM chip (rather unlikely), use the ARM setup.

[**Git for Windows/x64 Setup**](https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.4/Git-2.55.0.4-64-bit.exe)

[**Git for Windows/ARM64 Setup**](https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.4/Git-2.55.0.4-arm64.exe)

**macOS** — in the terminal, run:

```
xcode-select --install
```

A dialog appears. Click Install and wait. If it says the tools are already installed, you are done.

### Check

Open a **fresh** terminal and run:

```
git --version
```

You should see something like `git version 2.55.0`. The exact number does not matter.

### Then tell Git who you are

Git stamps your name onto everything you save, and it refuses to save anything until it knows what that name is. Setting it now takes ten seconds; not setting it stops you on day 1. Run these three commands, with your own name and the email address of your GitHub account:

```
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
```

The third one is not about you — it makes Git agree with GitHub about what the starting point of a project is called. Without it you get a warning every time you start one.

### Check

```
git config --global --list
```

The output contains your name, your email, and `init.defaultbranch=main`.

---

## Step 3 — uv

`uv` installs Python for you, creates the isolated environment your project needs, and runs your code inside it.

**Windows** — in the terminal:

```
winget install --id=astral-sh.uv -e
```

If `winget` is not available on your machine, use this instead:

```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS** — in the terminal:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

If you already use Homebrew, `brew install uv` works too.

### Check

Close the terminal, open a fresh one, then run:

```
uv --version
```

You should see something like `uv 0.12.3`.

---

## Step 4 — Sign in to GitHub

Because the repository is private, your laptop has to prove who you are before it can download it.

**Windows** — in the terminal:

```
winget install --id GitHub.cli -e
```

**macOS** — `brew install gh` if you use Homebrew. If you do not, download the macOS installer from [cli.github.com](https://cli.github.com) and run it.

Then close the terminal, **open a fresh one**, and run:

```
gh auth login
```

You will be asked a handful of questions. Answer them like this:

| Question                                       | Answer                       |
| ---------------------------------------------- | ---------------------------- |
| What account do you want to log into?          | **GitHub.com**               |
| What is your preferred protocol?               | **HTTPS**                    |
| Authenticate Git with your GitHub credentials? | **Yes**                      |
| How would you like to authenticate?            | **Login with a web browser** |

A one-time code appears in the terminal. Press Enter, paste the code into the browser page that opens, and approve it. The exact wording differs a little between versions; the answers above are what matter. Say **Yes** to the Git credentials question in particular — that is the one that makes step 5 work.

### Check

```
gh auth status
```

The output contains `Logged in to github.com account <your username>`.

---

## Step 5 — Get the code

### First, decide where the code should be saved

The terminal is always "standing" inside one folder, and `git clone` puts the code **there**. When you open a fresh terminal, that folder is your user folder — so if you clone right now, the code lands there (which is totally fine if you want that).

These five commands work the same on Windows and macOS:

| Command             | What it does                                 |
| ------------------- | -------------------------------------------- |
| `pwd`               | Shows which folder you are in right now      |
| `ls`                | Lists what is in it                          |
| `cd name_of_folder` | Goes into the folder called `name_of_folder` |
| `cd ..`             | Goes back up one folder                      |
| `cd ~`              | Goes to your user folder, wherever you were  |

If you have no folder in mind, make one. This puts it in your user folder and moves into it:

```
cd ~
mkdir cs4eng
cd cs4eng
```

> **Windows:** avoid `Desktop` and `Documents` folder if you use OneDrive. OneDrive tries to sync every file the project generates, which makes everything slow and occasionally locks files while you work. Your user folder, as above, is outside OneDrive. Do not use a USB stick or a network drive either.

### Check

```
pwd
```

It prints the folder you just chose — something like `C:\Users\you\projects` or `/Users/you/projects`. Whatever it prints is where the code is about to appear.

### Now get the code

```
git clone https://github.com/juli6999/cs4eng.git factoryflow-course
cd factoryflow-course
```

This creates a `factoryflow-course` folder inside the folder you chose above, and moves you into it.

> **This folder is the course material, and it stays read-only.** On the first morning you will create a second folder next to it — your own repository, with a name your group picks — and everything you build during the three days goes in there. You do not have to do anything about that now; just do not rename or tidy this one away.

### Check

```
ls
```

You see a `README.md`, a copy of this `SETUP.md`, and one folder per session — `s1-1-kickoff-warmup`, `s1-2-professional-workbench`, and so on down to `s3-6`.

That is the material for all three days. There is nothing to read in it beforehand; we open one folder at a time, together.

---

## Step 6 — Download packages

This command downloads everything the workshop needs and puts it in a cache on your machine.

```
uv run --no-project --with "pandas<3" python -c "import pandas; print('ready:', pandas.__version__)"
```

It does not matter which folder you are in, and it does not need the code from step 5 — so run it even if the clone did not work.

> **The first run is slow and quiet.** It can sit there for a few minutes with almost nothing on screen. That is normal. Leave it alone until you get your prompt back.

### Check

The last line printed is:

```
ready: 2.3.3
```

The version number may differ slightly. Anything that ends in `ready:` is fine.

---

## Step 7 — An editor

Bring whatever you already use. If you have no preference, install [Visual Studio Code](https://code.visualstudio.com) — it is free and it is the same on both systems.

After installing it, add the **Python** extension: open VS Code, click the squares icon in the left bar, search for `Python`, install the one published by Microsoft.

---

## Step 8 — Docker

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for your system, start it, and then run this in the terminal:

```
docker pull python:3.12-slim
```

### Check

```
docker run --rm python:3.12-slim python -c "print('containers work')"
```

prints `containers work`.

---

## When something goes wrong

| What you see                                               | What it means                                                                                                                                        | What to do                                                                                                         |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `uv: command not found` `'uv' is not recognized...`        | Your terminal was open before uv was installed                                                                                                       | Close the terminal window completely, open a new one, try again                                                    |
| `git: command not found`                                   | Same thing, for git                                                                                                                                  | Close and reopen the terminal                                                                                      |
| `gh: command not found`                                    | Same thing, for gh                                                                                                                                   | Close and reopen the terminal                                                                                      |
| `Repository not found` when cloning                        | The repository is private and your account is not on it yet. GitHub says "not found" rather than "not allowed", so this is **not** a typo in the URL | Check that you accepted the invitation email, then confirm with your facilitator that they have the right username |
| The clone asks for a username and password                 | Git is not using your GitHub sign-in                                                                                                                 | Run `gh auth setup-git`, then clone again. Never type your GitHub password here — it is always rejected            |
| `Authentication failed` on clone or push                   | Same cause                                                                                                                                           | Run `gh auth status`. If it says you are not logged in, redo step 4                                                |
| `No space left on device` / `not enough space on the disk` | Your drive filled up mid-download                                                                                                                    | Free up space, then run the command again — it picks up where it stopped                                           |
| You cannot find the `factoryflow` folder afterwards        | It was created wherever the terminal was standing                                                                                                    | Run `pwd` in that same terminal — that is where it is                                                              |
| `Author identity unknown` / `Please tell me who you are`   | Git does not know your name and email yet                                                                                                            | Run the three `git config --global` commands in step 2                                                             |
| The `curl` line on macOS does nothing                      | You are offline, or you are not in the terminal                                                                                                      | Check you are connected and in the terminal window, then retry                                                     |
| `running scripts is disabled on this system` (Windows)     | Script execution is blocked by policy                                                                                                                | Use the `winget` command instead                                                                                   |
| `Permission denied` on macOS                               | You typed `sudo` somewhere                                                                                                                           | Do not use `sudo` for any of these. Run them as yourself                                                           |

If a step still fails after one retry, **stop and ask your facilitator**.
