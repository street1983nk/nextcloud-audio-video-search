"""The hardened media intake (plan 03-05): ffprobe for the track, ffmpeg for the PCM.

Both work on a local temporary file only, never on a pipe from the gateway: an
MP4 with its index at the end cannot be read from a pipe (RESEARCH M-3).
"""
