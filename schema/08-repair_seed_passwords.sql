-- Repair the original seed hash, which cannot authenticate with Argon2.
-- The shared development password is 'password', as in scripts/seed.py.
-- Accounts with a changed password are unaffected. Safe to apply again.
UPDATE users
SET password_hash = '$argon2id$v=19$m=65536,t=3,p=4$p4qBpCxhtkldFlahR5lJ8w$yvfS/LY1KVu4TxM+AUzno6PxpuHq6s+EW3IXzjHUZE8'
WHERE password_hash = '$2b$12$e80MvQkK6Q5Z6XhF6Q6iK.b7fK.30s8nQoUu3zJbQf0aT7GqI7rGe';
