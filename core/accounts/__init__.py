"""Learner accounts and what is kept for them: users, teams, skill history and saved prospects.

Plain SQLite (stdlib) on the server, one file, no ORM. Nothing here knows about Flask: the routes in
backend/routes/account.py and team.py call these stores and decide what a request may see.

  db.py         the database file, connections, and schema migrations (one list, applied in order)
  passwords.py  password hashing (scrypt) and checking
  users.py      sign up, log in, look up, delete (deleting a user deletes everything kept for them)
  teams.py      a team with an invite code; members are reps or managers
  library.py    a learner's skill history and saved prospects
"""
