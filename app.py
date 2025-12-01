import streamlit as st
import sqlite3
import json
from datetime import datetime

DB_PATH = "orapa.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            secret_board TEXT,
            moves TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_game(game_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT secret_board, moves FROM games WHERE game_id=?", (game_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    board_json, moves_json = row
    board = json.loads(board_json)
    moves = json.loads(moves_json)
    return {"board": board, "moves": moves}

def save_game(game_id: str, board, moves):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO games (game_id, secret_board, moves, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(game_id) DO UPDATE SET
          secret_board=excluded.secret_board,
          moves=excluded.moves,
          updated_at=excluded.updated_at
    """, (
        game_id,
        json.dumps(board),
        json.dumps(moves),
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()


def create_initial_board():
    # Na razie: zwykła tablica 8x8 z zerami
    size = 8
    board = {
        "size": size,
        "data": [[0 for _ in range(size)] for _ in range(size)]
    }
    return board


def host_view(game_id, board, moves):
    st.subheader("Widok HOST (ukrywa planszę)")

    st.write("Twoja tajna plansza (placeholder):")
    st.json(board)  # później można zamienić na rysunek / siatkę

    st.markdown("### Ruchy gracza GUEST")
    if not moves:
        st.write("Brak ruchów.")
    else:
        for m in moves:
            st.write(m)

    st.markdown("### Odpowiedź na ostatni ruch")
    if moves:
        last = moves[-1]
        st.write(f"Ostatni ruch: {last}")
        answer = st.text_input("Twoja odpowiedź (np. 'pudło', 'trafiłeś', 'fala odbita w prawo')", key="host_answer")
        if st.button("Zapisz odpowiedź"):
            last["answer"] = answer
            save_game(game_id, board, moves)
            st.rerun()
    else:
        st.info("Czekasz na pierwszy ruch GUESTa.")


def guest_view(game_id, board, moves):
    st.subheader("Widok GUEST (zgaduje)")

    st.markdown("### Twoje ruchy i odpowiedzi")
    if not moves:
        st.write("Brak ruchów.")
    else:
        for m in moves:
            st.write(m)

    st.markdown("### Nowy ruch")
    col = st.number_input("Kolumna", min_value=0, max_value=board["size"] - 1, step=1)
    row = st.number_input("Wiersz", min_value=0, max_value=board["size"] - 1, step=1)

    if st.button("Wyślij ruch"):
        moves.append({
            "who": "GUEST",
            "col": int(col),
            "row": int(row),
            "time": datetime.utcnow().isoformat()
        })
        save_game(game_id, board, moves)
        st.rerun()

    st.caption("Odśwież stronę (Ctrl+R / przeciągnij w dół na telefonie), żeby zobaczyć nowe odpowiedzi HOSTa.")
    
def main():
    st.set_page_config(page_title="Orapa Mine Online", page_icon="💎")
    init_db()

    st.title("Orapa Mine – gra online dla 2 osób")

    role = st.radio("Wybierz rolę", ["HOST (ukrywa układ)", "GUEST (zgaduje)"])
    game_id = st.text_input("Nazwa pokoju (umówcie się na to samo hasło)")

    if not game_id:
        st.info("Wpisz nazwę pokoju, np. 'orapa123'.")
        return

    game = load_game(game_id)

    # HOST: tworzy nową grę, jeśli nie istnieje
    if game is None and "HOST" in role:
        st.success("Tworzę nową grę.")
        board = create_initial_board()
        moves = []
        save_game(game_id, board, moves)
        game = {"board": board, "moves": moves}

    if game is None and "GUEST" in role:
        st.error("Ta gra jeszcze nie istnieje. Poproś HOSTa, żeby ją utworzył.")
        return

    board = game["board"]
    moves = game["moves"]

    if "HOST" in role:
        host_view(game_id, board, moves)
    else:
        guest_view(game_id, board, moves)

if __name__ == "__main__":
    main()

