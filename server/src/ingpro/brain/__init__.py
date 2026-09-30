"""The learning "brain": neurons (things to learn), synapses (links between them) and the rules that change them.

SQLite is the source of truth (ADR-008); the Obsidian vault is a one-way projection of it (see vault.py).
The brain vocabulary is a design metaphor: each rule below is an explicit, testable choice inspired by the
named idea, not a simulation of real neurons.
"""
