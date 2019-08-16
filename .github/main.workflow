workflow "Continuous Integration" {
  on = "push"
  resolves = [
    "docker://cdssnc/seekret-github-action",
    "docker://python:3.6-stretch",
  ]
}

action "docker://cdssnc/seekret-github-action" {
  uses = "docker://cdssnc/seekret-github-action"
}

action "docker://python:3.6-stretch" {
  uses = "docker://python:3.6-stretch"
  runs = ["/bin/bash", "-c", "pip3 install -r requirements-dev.txt && make test"]
}