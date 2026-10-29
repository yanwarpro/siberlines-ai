"""Test koneksi database Supabase."""
import sys
import urllib.parse

from sqlalchemy import create_engine, text

# Password asli (tanpa escaping shell)
PASSWORD = "Y/Dzm$m4$Z4#3zP"
PROJECT = "elaakpvyxpzvfzcbjjtq"
POOLER = "aws-0-eu-west-1.pooler.supabase.com"
DB_NAME = "postgres"

encoded_pw = urllib.parse.quote(PASSWORD, safe="")
print(f"Password original : {PASSWORD}")
print(f"Password encoded  : {encoded_pw}")
print()

def test_connection(label, url):
    print(f"[TEST] {label}")
    try:
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 15},
        )
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            row = result.fetchone()
            print(f"  ✅ Berhasil!")
            print(f"  PostgreSQL: {row[0][:80]}")
            return True
    except Exception as e:
        print(f"  ❌ Gagal: {e}")
        return False
    finally:
        print()


# 1. Pooler Session mode (port 5432) - user: postgres.PROJECT
url1 = f"postgresql+psycopg://postgres.{PROJECT}:{encoded_pw}@{POOLER}:5432/{DB_NAME}"
ok1 = test_connection("Pooler Session mode (port 5432)", url1)

# 2. Pooler Transaction mode (port 6543)
url2 = f"postgresql+psycopg://postgres.{PROJECT}:{encoded_pw}@{POOLER}:6543/{DB_NAME}"
ok2 = test_connection("Pooler Transaction mode (port 6543)", url2)

# 3. Direct DB (fallback, mungkin perlu IPv6)
direct_url = f"postgresql+psycopg://postgres:{encoded_pw}@db.{PROJECT}.supabase.co:5432/{DB_NAME}"
ok3 = test_connection("Direct DB connection (port 5432)", direct_url)

if ok1 or ok2 or ok3:
    print("✅ SUKSES: Koneksi database berhasil!")
    if ok1:
        print(f"   Gunakan: {url1[:70]}...")
    elif ok2:
        print(f"   Gunakan: {url2[:70]}...")
else:
    print("❌ GAGAL: Semua metode koneksi gagal.")
    print()
    print("Kemungkinan penyebab:")
    print("  1. Password salah / sudah berubah di Supabase dashboard")
    print("  2. IP Anda diblokir (cek Supabase Network Restrictions)")
    print("  3. Project belum sepenuhnya aktif")
    sys.exit(1)
