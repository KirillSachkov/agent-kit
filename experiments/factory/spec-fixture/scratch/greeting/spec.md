# Greeting

## Problem Statement

The greeter prints a placeholder instead of greeting the person named on the command line.

## Solution

`python3 greet.py <name>` greets that person, reports a missing name, and can shout.

## User Stories

1. As a user, I want `python3 greet.py Ada` to print `Hello, Ada!`, so that the tool greets me by name.
2. As a user, I want a clear error when I pass no name, so that I know how to call the tool.
3. As a user, I want `--shout` to print the greeting in capitals, so that I can be loud.

## Testing Decisions

Test the command as a subprocess, per the project's testing strategy.

**Stage:** ready
