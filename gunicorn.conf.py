# Gunicorn reads this file automatically from the working directory.
# Sessions live in process memory (backend/security.py), so every request must
# reach the same process: one worker, with threads for concurrency.
workers = 1
threads = 8
