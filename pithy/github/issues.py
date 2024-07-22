
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Issue:
  active_lock_reason: str|None
  assignee:User|None
  assignees: list[User]
  author_association: str
  body:str|None
  closed_at:str|None
  comments: int
  comments_url: str
  created_at: str
  events_url: str
  html_url: str
  id: int
  labels: list[Label]
  labels_url: str
  locked: bool
  milestone:str|None
  node_id: str
  number: int
  performed_via_github_app:str|None
  reactions: dict[str,int|str]
  repository_url: str
  state: str
  state_reason:str|None
  timeline_url: str
  title: str
  updated_at: str
  url: str
  user: User
  draft: bool = False
  pull_request:PullRequest|None = None


@dataclass
class Label:
  color: str
  default: bool
  description: str
  id: int
  name: str
  node_id: str
  url: str


@dataclass
class PullRequest:
  diff_url: str
  html_url: str
  merged_at:str|None
  patch_url: str
  url: str


@dataclass
class User:
  avatar_url: str
  events_url: str
  followers_url: str
  following_url: str
  gists_url: str
  gravatar_id: str
  html_url: str
  id: int
  login: str
  node_id: str
  organizations_url: str
  received_events_url: str
  repos_url: str
  site_admin: bool
  starred_url: str
  subscriptions_url: str
  type: str
  url: str


def main() -> None:
  from argparse import ArgumentParser, FileType

  from ..io import outM
  from ..loader import load
  from ..transtruct import Transtructor

  parser = ArgumentParser(description=__doc__)
  parser.add_argument('files', nargs='+', type=FileType('r'), help='Input files to generate schemas from.')

  parser.add_argument('-output', type=FileType('w'), default='-',
    help='Output file to write schemas to. Default: stdout.')

  args = parser.parse_args()

  transtructor = Transtructor()

  for file in args.files:
    nodes = load(file)
    issues = transtructor.transtruct(nodes, list[Issue])
    outM(file.name, issues)


if __name__ == '__main__': main()
