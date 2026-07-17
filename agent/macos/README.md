# agent/macos

macOS PTY backend — same POSIX approach as `../linux` (`ptyprocess`/
`forkpty`), so this is mostly a packaging task: notarized `.app` or
Homebrew formula, `launchd` agent instead of systemd. Not yet implemented.
