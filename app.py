import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import string
from shapely.geometry import Polygon
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------
# Konfiguracja plansz (dwa widoki)
# ---------------------------------------------------------
BOARD_CONFIGS = {
    "zielona": {
        "label": "Twoja plansza",
        "bg": "#88cc88",
    },
    "fioletowa": {
        "label": "Plansza Przeciwnika",
        "bg": "#e3ccff",
    },
}

# Ikony kolorów (dla przycisków)
Y_ICON = "🟨"   # żółty trójkąt
W_ICON = "⬜"   # białe figury + przezroczysty trójkąt
B_ICON = "🟦"   # niebieski trójkąt + jasnoniebieski kwadrat
R_ICON = "🟥"   # czerwony równoległobok

ROWS = 8
COLS = 10


# ---------------------------------------------------------
# Stan JEDNEJ planszy
# ---------------------------------------------------------
def make_single_board():
    return {
        # Żółty trójkąt
        "y_cx": 3.0,
        "y_cy": 3.0,
        "y_ori": 0,
        # Biały trójkąt
        "w_cx": 3.0,
        "w_cy": 5.0,
        "w_ori": 0,
        # Niebieski trójkąt
        "b_cx": 7.0,
        "b_cy": 3.0,
        "b_ori": 0,
        # Biały kwadrat (romb)
        "s_cx": 6.0,
        "s_cy": 6.0,
        "s_ori": 0,
        # Czerwony równoległobok
        "r_cx": 4.0,
        "r_cy": 2.0,
        "r_ori": 0,
        "r_flip": False,
        # Przezroczysty trójkąt (hyp = 2)
        "t2_cx": 2.0,
        "t2_cy": 2.0,
        "t2_ori": 0,
        # Jasnoniebieski kwadrat 1x1
        "lb_x": 1.0,
        "lb_y": 1.0,
        # Status sprawdzania
        "layout_valid": None,
        "layout_msg": "",
    }


def make_empty_boards():
    """Dwie plansze: Twoja + Twoje zgadywanie przeciwnika (obie prywatne)."""
    return {
        "zielona": make_single_board(),
        "fioletowa": make_single_board(),
    }


# ---------------------------------------------------------
# Globalny magazyn POKOI (wspólny tylko dla czatu i stanu gry)
# rooms = {
#   room_code: {
#       "chat": [...],
#       "players": {
#           nickname: {
#               "ready": bool,
#               "green_locked": dict | None
#           },
#       },
#       "game_over": bool,
#       "winner": str | None
#   }
# }
# ---------------------------------------------------------
@st.cache_resource
def get_rooms():
    return {}


rooms = get_rooms()


def ensure_room(room_code: str):
    if room_code not in rooms:
        rooms[room_code] = {
            "chat": [],
            "players": {},
            "game_over": False,
            "winner": None,
        }
    return rooms[room_code]


def ensure_player_entry(room_data, nickname: str):
    players = room_data.setdefault("players", {})
    if nickname not in players:
        players[nickname] = {
            "ready": False,
            "green_locked": None,
        }
    return players[nickname]


def boards_equal(b1, b2, tol=1e-6):
    """Porównuje dwa stany planszy (pozycje/obroty figur)."""
    if b1 is None or b2 is None:
        return False
    keys = [
        "y_cx", "y_cy", "y_ori",
        "w_cx", "w_cy", "w_ori",
        "b_cx", "b_cy", "b_ori",
        "s_cx", "s_cy", "s_ori",
        "r_cx", "r_cy", "r_ori", "r_flip",
        "t2_cx", "t2_cy", "t2_ori",
        "lb_x", "lb_y",
    ]
    for k in keys:
        v1 = b1.get(k)
        v2 = b2.get(k)
        if isinstance(v1, float) or isinstance(v2, float):
            if v1 is None or v2 is None or abs(v1 - v2) > tol:
                return False
        else:
            if v1 != v2:
                return False
    return True


# ---------------------------------------------------------
# Konfiguracja strony
# ---------------------------------------------------------
st.set_page_config(page_title="Orapa online", layout="wide")
st.markdown(
    """
    <h1 style="text-align:center;">
        ORAPA online
    </h1>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# LOBBY – wybór pokoju (Enter zatwierdza)
# ---------------------------------------------------------
if "room_input" not in st.session_state:
    st.session_state.room_input = ""
if "room_code" not in st.session_state:
    st.session_state.room_code = ""

room_input = st.text_input(
    "Kod pokoju (umów się z drugim graczem, np. ABC123)",
    value=st.session_state.room_input,
    key="room_input",
)

room_code = room_input.strip()
st.session_state.room_code = room_code

if not room_code:
    st.warning("Podaj kod pokoju i naciśnij Enter, żeby zacząć grę.")
    st.stop()

# --- Nazwa gracza widoczna w czacie ---
if "nickname" not in st.session_state:
    st.session_state.nickname = ""

nick_input = st.text_input(
    "Twoja nazwa w czacie (widoczna dla innych w tym pokoju)",
    value=st.session_state.nickname,
    max_chars=20,
)

nick_clean = nick_input.strip()

if not nick_clean:
    st.info("Podaj najpierw swoją nazwę, wtedy pojawią się plansze i czat.")
    st.stop()

st.session_state.nickname = nick_clean
nickname = st.session_state.nickname

# Autoodświeżanie całej appki co 1.5 s (czat + stan gry)
st_autorefresh(interval=1500, key="chat_autorefresh")

# ---------------------------------------------------------
# Inicjalizacja pokoju i gracza
# ---------------------------------------------------------
room_data = ensure_room(room_code)
player_entry = ensure_player_entry(room_data, nickname)
players = room_data["players"]

# ---------------------------------------------------------
# Inicjalizacja prywatnych plansz w sesji
# ---------------------------------------------------------
if "boards" not in st.session_state:
    st.session_state.boards = make_empty_boards()

if "current_board" not in st.session_state:
    st.session_state.current_board = "zielona"

board_key = st.session_state.current_board  # "zielona" albo "fioletowa"
boards = st.session_state.boards
state = boards[board_key]

BG_COLOR = BOARD_CONFIGS[board_key]["bg"]
board_title = BOARD_CONFIGS[board_key]["label"]

# Sterowanie figurami:
# - na zielonej planszy blokujemy edycję po START (ready=True)
# - na fioletowej planszy zawsze można edytować (zgadywanie)
controls_enabled = not (board_key == "zielona" and player_entry["ready"])


# ---------------------------------------------------------
# Geometria figur (bazowa w (0,0))
# ---------------------------------------------------------
BASE_YELLOW = np.array([
    [-1.0, -1.0],
    [ 1.0, -1.0],
    [-1.0,  1.0],
])

BASE_SMALL_TRI = np.array([
    [-2.0,  0.0],
    [ 2.0,  0.0],
    [ 0.0,  2.0],
])

BASE_SQUARE_DIAMOND = np.array([
    [-1.0,  0.0],
    [ 0.0, -1.0],
    [ 1.0,  0.0],
    [ 0.0,  1.0],
])

SCALE_TRI2 = 0.9
BASE_TRI_HYP2 = SCALE_TRI2 * np.array([
    [-1.0, 0.0],
    [ 1.0, 0.0],
    [ 0.0, 1.0],
])

BASE_PAR_INT = np.array([
    [0.0, 0.0],
    [2.0, 0.0],
    [3.0, 1.0],
    [1.0, 1.0],
])

ROT_MATS = [
    np.array([[1.0, 0.0],
              [0.0, 1.0]]),
    np.array([[0.0, -1.0],
              [1.0,  0.0]]),
    np.array([[-1.0,  0.0],
              [ 0.0, -1.0]]),
    np.array([[ 0.0, 1.0],
              [-1.0, 0.0]]),
]


def yellow_vertices(cx, cy, ori):
    M = ROT_MATS[ori % 4]
    offs = BASE_YELLOW @ M.T
    return offs + np.array([cx, cy])


def small_tri_vertices(cx, cy, ori):
    M = ROT_MATS[ori % 4]
    offs = BASE_SMALL_TRI @ M.T
    return offs + np.array([cx, cy])


def square_diamond_vertices(cx, cy, ori):
    M = ROT_MATS[ori % 4]
    offs = BASE_SQUARE_DIAMOND @ M.T
    return offs + np.array([cx, cy])


def tri_hyp2_vertices(cx, cy, ori):
    M = ROT_MATS[ori % 4]
    offs = BASE_TRI_HYP2 @ M.T
    return offs + np.array([cx, cy])


def red_vertices(rx, ry, ori, flip):
    base = BASE_PAR_INT.copy()
    if flip:
        base[:, 0] *= -1.0
    M = ROT_MATS[ori % 4]
    offs = base @ M.T
    return offs + np.array([rx, ry])


def lightblue_vertices(lx, ly):
    base = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [0.0, 1.0],
    ])
    return base + np.array([lx, ly])


def clamp_center(cx, cy, ori, vertex_func):
    verts = vertex_func(cx, cy, ori)
    minx, maxx = verts[:, 0].min(), verts[:, 0].max()
    miny, maxy = verts[:, 1].min(), verts[:, 1].max()

    if minx < 0:
        cx += -minx
    if maxx > COLS:
        cx -= (maxx - COLS)

    verts = vertex_func(cx, cy, ori)
    miny, maxy = verts[:, 1].min(), verts[:, 1].max()

    if miny < 0:
        cy += -miny
    if maxy > ROWS:
        cy -= (maxy - ROWS)

    return float(cx), float(cy)


def clamp_parallelogram(rx, ry, ori, flip):
    verts = red_vertices(rx, ry, ori, flip)
    minx, maxx = verts[:, 0].min(), verts[:, 0].max()
    miny, maxy = verts[:, 1].min(), verts[:, 1].max()

    if minx < 0:
        rx += -minx
    if maxx > COLS:
        rx -= (maxx - COLS)

    verts = red_vertices(rx, ry, ori, flip)
    miny, maxy = verts[:, 1].min(), verts[:, 1].max()

    if miny < 0:
        ry += -miny
    if maxy > ROWS:
        ry -= (maxy - ROWS)

    return float(round(rx)), float(round(ry))


def clamp_lightblue(lx, ly):
    verts = lightblue_vertices(lx, ly)
    minx, maxx = verts[:, 0].min(), verts[:, 0].max()
    miny, maxy = verts[:, 1].min(), verts[:, 1].max()

    if minx < 0:
        lx += -minx
    if maxx > COLS:
        lx -= (maxx - COLS)
    if miny < 0:
        ly += -miny
    if maxy > ROWS:
        ly -= (maxy - ROWS)

    return float(lx), float(ly)


# ---------------------------------------------------------
# Poligony i sprawdzanie ułożenia (dla JEDNEJ planszy/state)
# ---------------------------------------------------------
def get_all_polygons(state):
    shapes = []

    shapes.append(("Żółty trójkąt",
                   Polygon(yellow_vertices(state["y_cx"],
                                           state["y_cy"],
                                           state["y_ori"]))))

    shapes.append(("Biały trójkąt",
                   Polygon(small_tri_vertices(state["w_cx"],
                                              state["w_cy"],
                                              state["w_ori"]))))

    shapes.append(("Niebieski trójkąt",
                   Polygon(small_tri_vertices(state["b_cx"],
                                              state["b_cy"],
                                              state["b_ori"]))))

    shapes.append(("Biały kwadrat",
                   Polygon(square_diamond_vertices(state["s_cx"],
                                                   state["s_cy"],
                                                   state["s_ori"]))))

    shapes.append(("Czerwony równoległobok",
                   Polygon(red_vertices(state["r_cx"],
                                        state["r_cy"],
                                        state["r_ori"],
                                        state["r_flip"]))))

    shapes.append(("Przezroczysty trójkąt",
                   Polygon(tri_hyp2_vertices(state["t2_cx"],
                                             state["t2_cy"],
                                             state["t2_ori"]))))

    shapes.append(("Jasnoniebieski kwadrat",
                   Polygon(lightblue_vertices(state["lb_x"],
                                              state["lb_y"]))))

    fixed = []
    for name, poly in shapes:
        if not poly.is_valid:
            poly = poly.buffer(0)
        fixed.append((name, poly))
    return fixed


def check_layout(state):
    shapes = get_all_polygons(state)
    eps_area = 1e-6

    for i in range(len(shapes)):
        name_i, poly_i = shapes[i]
        for j in range(i + 1, len(shapes)):
            name_j, poly_j = shapes[j]

            inter = poly_i.intersection(poly_j)
            if inter.is_empty:
                continue

            geoms = [inter]
            if inter.geom_type == "GeometryCollection":
                geoms = list(inter.geoms)

            # 1) Nachodzenie (pole > 0)
            for g in geoms:
                if g.geom_type in ("Polygon", "MultiPolygon") and g.area > eps_area:
                    return False, f"Figury {name_i} i {name_j} nachodzą na siebie."

            # 2) Styk bokami (odcinki)
            for g in geoms:
                if g.geom_type in ("LineString", "MultiLineString"):
                    return False, f"Figury {name_i} i {name_j} stykają się bokami."

            # 3) Więcej niż jeden punkt wspólny
            point_count = 0
            for g in geoms:
                if g.geom_type == "Point":
                    point_count += 1
                elif g.geom_type == "MultiPoint":
                    point_count += len(g.geoms)

            if point_count > 1:
                return False, f"Figury {name_i} i {name_j} mają więcej niż jeden punkt wspólny."

    return True, "Ułożenie jest poprawne – figury nie nachodzą na siebie i nie stykają się bokami."


# ---------------------------------------------------------
# Rysowanie planszy
# ---------------------------------------------------------
def draw_board(state, bg_color):
    fig, ax = plt.subplots(figsize=(4.5, 4))

    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)

    ax.set_xlim(-0.5, COLS + 0.5)
    ax.set_ylim(-0.5, ROWS + 0.5)

    for x in range(COLS + 1):
        ax.plot([x, x], [0, ROWS], color="white", linewidth=1, zorder=0)
    for y in range(ROWS + 1):
        ax.plot([0, COLS], [y, y], color="white", linewidth=1, zorder=0)

    def row_y(r):
        return ROWS - 0.5 - r

    for x in range(COLS):
        ax.text(
            x + 0.5, ROWS + 0.45, str(x + 1),
            ha="center", va="center", color="white", fontsize=12, zorder=0
        )

    bottom_labels = list(string.ascii_uppercase[8:8 + COLS])
    for x, label in enumerate(bottom_labels):
        ax.text(
            x + 0.5, -0.45, label,
            ha="center", va="center", color="white", fontsize=12, zorder=0
        )

    left_labels = list(string.ascii_uppercase[:ROWS])
    for r, label in enumerate(left_labels):
        ax.text(
            -0.45, row_y(r), label,
            ha="center", va="center", color="white", fontsize=12, zorder=0
        )

    for r in range(ROWS):
        ax.text(
            COLS + 0.45, row_y(r), str(11 + r),
            ha="center", va="center", color="white", fontsize=12, zorder=0
        )

    # Figury

    # Żółty
    verts_y = yellow_vertices(state["y_cx"], state["y_cy"], state["y_ori"])
    tri_y = patches.Polygon(
        verts_y, closed=True,
        facecolor="yellow", edgecolor="yellow",
        alpha=1.0, zorder=3
    )
    ax.add_patch(tri_y)

    # Biały trójkąt
    verts_w = small_tri_vertices(state["w_cx"], state["w_cy"], state["w_ori"])
    tri_w = patches.Polygon(
        verts_w, closed=True,
        facecolor="white", edgecolor="white",
        alpha=1.0, zorder=3
    )
    ax.add_patch(tri_w)

    # Niebieski trójkąt
    verts_b = small_tri_vertices(state["b_cx"], state["b_cy"], state["b_ori"])
    tri_b = patches.Polygon(
        verts_b, closed=True,
        facecolor="blue", edgecolor="blue",
        alpha=1.0, zorder=3
    )
    ax.add_patch(tri_b)

    # Biały romb
    verts_s = square_diamond_vertices(state["s_cx"], state["s_cy"], state["s_ori"])
    sq = patches.Polygon(
        verts_s, closed=True,
        facecolor="white", edgecolor="white",
        alpha=1.0, zorder=3
    )
    ax.add_patch(sq)

    # Czerwony równoległobok
    verts_r = red_vertices(
        state["r_cx"], state["r_cy"],
        state["r_ori"], state["r_flip"]
    )
    par = patches.Polygon(
        verts_r, closed=True,
        facecolor="red", edgecolor="red",
        alpha=1.0, zorder=3
    )
    ax.add_patch(par)

    # Przezroczysty trójkąt (hyp=2) – wypełnienie w kolorze tła
    verts_t2 = tri_hyp2_vertices(state["t2_cx"], state["t2_cy"], state["t2_ori"])
    tri2 = patches.Polygon(
        verts_t2, closed=True,
        facecolor=bg_color, edgecolor="white",
        linewidth=4.0, alpha=1.0, zorder=3
    )
    ax.add_patch(tri2)

    # Jasnoniebieski kwadrat 1x1
    verts_lb = lightblue_vertices(state["lb_x"], state["lb_y"])
    sq_lb = patches.Polygon(
        verts_lb, closed=True,
        facecolor="#66c2ff", edgecolor="#66c2ff",
        alpha=1.0, zorder=3
    )
    ax.add_patch(sq_lb)

    ax.axis("off")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------
# Pomocnicze – nagłówek figury (wycentrowany)
# ---------------------------------------------------------
def figure_header(container, text, color_hex, black_override=False):
    txt_color = "#000000" if black_override else color_hex
    container.markdown(
        f"""
        <h3 style="
            color:{txt_color};
            margin-bottom:0.3rem;
            text-align:center;
        ">{text}</h3>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Funkcja wysyłania wiadomości czatu (Enter)
# ---------------------------------------------------------
def send_message():
    txt = st.session_state.get("chat_input", "").strip()
    if not txt:
        return

    room_code_local = st.session_state.room_code
    rooms_local = get_rooms()
    room_data_local = ensure_room(room_code_local)
    chat_log_local = room_data_local.setdefault("chat", [])
    nickname_local = st.session_state.nickname

    chat_log_local.append({"author": nickname_local, "text": txt})

    # wyczyść pole po wysłaniu
    st.session_state.chat_input = ""



# ---------------------------------------------------------
# Pasek info o zakończeniu gry
# ---------------------------------------------------------
if room_data["game_over"]:
    w = room_data["winner"]
    if w == nickname:
        st.success("Gra zakończona. Wygrałeś!")
    else:
        st.warning(f"Gra zakończona. Wygrał {w}.")


# ---------------------------------------------------------
# Layout: dwie kolumny sterowania + plansza + prawa kolumna (czat)
# ---------------------------------------------------------
controls_col1, controls_col2, board_col, right_col = st.columns([0.4, 0.4, 1.6, 1.0])

# PRAWY BOK: czat
with right_col:
    st.markdown("### Czat pokoju")

    chat_log = room_data.setdefault("chat", [])

    # zbuduj HTML dla wszystkich wiadomości
    chat_items_html = ""
    for msg in chat_log[-100:]:
        author = msg.get("author", "Anonim")
        text = msg.get("text", "")

        if author == nickname:
            bg = "#ffffff"      # moje
        elif author == "SYSTEM":
            bg = "#dddddd"      # system
        else:
            bg = "#f3e6ff"      # przeciwnik

        chat_items_html += f"""
<div style="background-color:{bg}; padding:6px 8px; margin-bottom:4px;
            border-radius:6px; font-size:0.9rem;">
    <strong>{author}:</strong> {text}
</div>
"""

    # scrollbox + JS autoscroll
    scrollbox_html = f"""
<div id="chat-box" style="height:400px; overflow-y:auto; padding:6px;
            border:1px solid #cccccc; border-radius:6px;
            background-color:#fdfdfd;">
    {chat_items_html}
</div>
<script>
    var chatBox = document.getElementById('chat-box');
    if (chatBox) {{
        chatBox.scrollTop = chatBox.scrollHeight;
    }}
</script>
"""

    st.markdown(scrollbox_html, unsafe_allow_html=True)

    # input – Enter wysyła, po wysłaniu send_message czyści pole
    st.text_input(
        "Twoja wiadomość (Enter wysyła)",
        key="chat_input",
        on_change=send_message,
    )




# ---------------------------------------------------------
# KOLUMNA STEROWANIA 1
# ---------------------------------------------------------
with controls_col1:

    # ---------------- Żółty trójkąt ----------------
    figure_header(controls_col1, "Żółty trójkąt", "#ffd000")

    row_y1 = st.columns(3)
    if controls_enabled and row_y1[0].button(f"{Y_ICON}⟲", key="y_rot_left"):
        state["y_ori"] = (state["y_ori"] + 1) % 4
    if controls_enabled and row_y1[1].button(f"{Y_ICON}⬆️", key="y_up"):
        state["y_cy"] += 1
    if controls_enabled and row_y1[2].button(f"{Y_ICON}⟳", key="y_rot_right"):
        state["y_ori"] = (state["y_ori"] - 1) % 4

    row_y2 = st.columns(3)
    if controls_enabled and row_y2[0].button(f"{Y_ICON}⬅️", key="y_left"):
        state["y_cx"] -= 1
    if controls_enabled and row_y2[1].button(f"{Y_ICON}⬇️", key="y_down"):
        state["y_cy"] -= 1
    if controls_enabled and row_y2[2].button(f"{Y_ICON}➡️", key="y_right"):
        state["y_cx"] += 1

    state["y_cx"], state["y_cy"] = clamp_center(
        state["y_cx"], state["y_cy"],
        state["y_ori"], yellow_vertices
    )

    st.markdown("---")

    # ---------------- Biały trójkąt ----------------
    figure_header(controls_col1, "Biały trójkąt", "#ffffff", black_override=True)

    row_w1 = st.columns(3)
    if controls_enabled and row_w1[0].button(f"{W_ICON}⟲", key="w_rot_left"):
        state["w_ori"] = (state["w_ori"] + 1) % 4
    if controls_enabled and row_w1[1].button(f"{W_ICON}⬆️", key="w_up"):
        state["w_cy"] += 1
    if controls_enabled and row_w1[2].button(f"{W_ICON}⟳", key="w_rot_right"):
        state["w_ori"] = (state["w_ori"] - 1) % 4

    row_w2 = st.columns(3)
    if controls_enabled and row_w2[0].button(f"{W_ICON}⬅️", key="w_left"):
        state["w_cx"] -= 1
    if controls_enabled and row_w2[1].button(f"{W_ICON}⬇️", key="w_down"):
        state["w_cy"] -= 1
    if controls_enabled and row_w2[2].button(f"{W_ICON}➡️", key="w_right"):
        state["w_cx"] += 1

    state["w_cx"], state["w_cy"] = clamp_center(
        state["w_cx"], state["w_cy"],
        state["w_ori"], small_tri_vertices
    )

    st.markdown("---")

    # ---------------- Niebieski trójkąt ----------------
    figure_header(controls_col1, "Niebieski trójkąt", "#3399ff")

    row_b1 = st.columns(3)
    if controls_enabled and row_b1[0].button(f"{B_ICON}⟲", key="b_rot_left"):
        state["b_ori"] = (state["b_ori"] + 1) % 4
    if controls_enabled and row_b1[1].button(f"{B_ICON}⬆️", key="b_up"):
        state["b_cy"] += 1
    if controls_enabled and row_b1[2].button(f"{B_ICON}⟳", key="b_rot_right"):
        state["b_ori"] = (state["b_ori"] - 1) % 4

    row_b2 = st.columns(3)
    if controls_enabled and row_b2[0].button(f"{B_ICON}⬅️", key="b_left"):
        state["b_cx"] -= 1
    if controls_enabled and row_b2[1].button(f"{B_ICON}⬇️", key="b_down"):
        state["b_cy"] -= 1
    if controls_enabled and row_b2[2].button(f"{B_ICON}➡️", key="b_right"):
        state["b_cx"] += 1

    state["b_cx"], state["b_cy"] = clamp_center(
        state["b_cx"], state["b_cy"],
        state["b_ori"], small_tri_vertices
    )

    st.markdown("---")

    # ---------------- Jasnoniebieski kwadrat ----------------
    figure_header(controls_col1, "Jasnoniebieski kwadrat", "#66c2ff")

    row_lb1 = st.columns(3)
    if controls_enabled and row_lb1[1].button(f"{B_ICON}⬆️", key="lb_up"):
        state["lb_y"] += 1

    row_lb2 = st.columns(3)
    if controls_enabled and row_lb2[0].button(f"{B_ICON}⬅️", key="lb_left"):
        state["lb_x"] -= 1
    if controls_enabled and row_lb2[1].button(f"{B_ICON}⬇️", key="lb_down"):
        state["lb_y"] -= 1
    if controls_enabled and row_lb2[2].button(f"{B_ICON}➡️", key="lb_right"):
        state["lb_x"] += 1

    state["lb_x"], state["lb_y"] = clamp_lightblue(
        state["lb_x"], state["lb_y"]
    )


# ---------------------------------------------------------
# KOLUMNA STEROWANIA 2
# ---------------------------------------------------------
with controls_col2:

    # ---------------- Biały kwadrat ----------------
    figure_header(controls_col2, "Biały kwadrat", "#ffffff", black_override=True)

    row_s1 = st.columns(3)
    if controls_enabled and row_s1[1].button(f"{W_ICON}⬆️", key="s_up"):
        state["s_cy"] += 1

    row_s2 = st.columns(3)
    if controls_enabled and row_s2[0].button(f"{W_ICON}⬅️", key="s_left"):
        state["s_cx"] -= 1
    if controls_enabled and row_s2[1].button(f"{W_ICON}⬇️", key="s_down"):
        state["s_cy"] -= 1
    if controls_enabled and row_s2[2].button(f"{W_ICON}➡️", key="s_right"):
        state["s_cx"] += 1

    state["s_cx"], state["s_cy"] = clamp_center(
        state["s_cx"], state["s_cy"],
        state["s_ori"], square_diamond_vertices
    )

    st.markdown("---")

    # ---------------- Czerwony równoległobok ----------------
    figure_header(controls_col2, "Czerwony równoległobok", "#ff3333")

    row_r1 = st.columns(4)
    if controls_enabled and row_r1[0].button(f"{R_ICON}⟲", key="r_rot_left"):
        state["r_ori"] = (state["r_ori"] + 1) % 4
    if controls_enabled and row_r1[1].button(f"{R_ICON}⬆️", key="r_up"):
        state["r_cy"] += 1
    if controls_enabled and row_r1[2].button(f"{R_ICON}⟳", key="r_rot_right"):
        state["r_ori"] = (state["r_ori"] - 1) % 4
    if controls_enabled and row_r1[3].button(f"{R_ICON}🔁", key="r_flip_btn"):
        state["r_flip"] = not state["r_flip"]

    row_r2 = st.columns(3)
    if controls_enabled and row_r2[0].button(f"{R_ICON}⬅️", key="r_left"):
        state["r_cx"] -= 1
    if controls_enabled and row_r2[1].button(f"{R_ICON}⬇️", key="r_down"):
        state["r_cy"] -= 1
    if controls_enabled and row_r2[2].button(f"{R_ICON}➡️", key="r_right"):
        state["r_cx"] += 1

    state["r_cx"], state["r_cy"] = clamp_parallelogram(
        state["r_cx"], state["r_cy"],
        state["r_ori"], state["r_flip"]
    )

    st.markdown("---")

    # ---------------- Przezroczysty trójkąt ----------------
    figure_header(controls_col2, "Przezroczysty trójkąt",
                  BG_COLOR, black_override=True)

    row_t2_1 = st.columns(3)
    if controls_enabled and row_t2_1[0].button(f"{W_ICON}⟲", key="t2_rot_left"):
        state["t2_ori"] = (state["t2_ori"] + 1) % 4
    if controls_enabled and row_t2_1[1].button(f"{W_ICON}⬆️", key="t2_up"):
        state["t2_cy"] += 1
    if controls_enabled and row_t2_1[2].button(f"{W_ICON}⟳", key="t2_rot_right"):
        state["t2_ori"] = (state["t2_ori"] - 1) % 4

    row_t2_2 = st.columns(3)
    if controls_enabled and row_t2_2[0].button(f"{W_ICON}⬅️", key="t2_left"):
        state["t2_cx"] -= 1
    if controls_enabled and row_t2_2[1].button(f"{W_ICON}⬇️", key="t2_down"):
        state["t2_cy"] -= 1
    if controls_enabled and row_t2_2[2].button(f"{W_ICON}➡️", key="t2_right"):
        state["t2_cx"] += 1

    state["t2_cx"], state["t2_cy"] = clamp_center(
        state["t2_cx"], state["t2_cy"],
        state["t2_ori"], tri_hyp2_vertices
    )

    st.markdown("---")

    # ---------------- PRZYCISK SPRAWDZANIA UKŁADU (dla aktualnej planszy) ----------------
    figure_header(controls_col2, "Sprawdzenie ułożenia (aktualna plansza)", "#ffffff", black_override=True)

    row_check = st.columns([1, 0.2])

    with row_check[0]:
        if st.button("Sprawdź ułożenie", key="check_layout"):
            valid, msg = check_layout(state)
            state["layout_valid"] = valid
            state["layout_msg"] = msg

    with row_check[1]:
        status = state["layout_valid"]
        if status is True:
            st.markdown("<span style='font-size: 1.8rem;'>✅</span>", unsafe_allow_html=True)
        elif status is False:
            st.markdown("<span style='font-size: 1.8rem;'>❌</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='font-size: 1.8rem;'>&nbsp;</span>", unsafe_allow_html=True)

    if state["layout_valid"] is True:
        st.success(state["layout_msg"])
    elif state["layout_valid"] is False:
        st.error(state["layout_msg"])
    else:
        st.markdown("_Kliknij przycisk, żeby sprawdzić ułożenie figur na tej planszy._")


# ---------------------------------------------------------
# Plansza – prawa duża kolumna + przycisk przełączania + START/ZAKOŃCZ/RESTART
# ---------------------------------------------------------
with board_col:
    title_row = st.columns([0.7, 0.3])
    with title_row[0]:
        st.markdown(
            f"<h2 style='text-align:center; margin-top:0;'>{board_title}</h2>",
            unsafe_allow_html=True,
        )
    with title_row[1]:
        st.markdown("&nbsp;")
        if st.button("Przełącz planszę", key="switch_board"):
            if st.session_state.current_board == "zielona":
                st.session_state.current_board = "fioletowa"
            else:
                st.session_state.current_board = "zielona"
            st.experimental_rerun()

    fig = draw_board(state, BG_COLOR)
    st.pyplot(fig)

    if board_key == "zielona" and player_entry["ready"]:
        st.info("Twoja plansza została zatwierdzona po START i jest zablokowana.")


    # -------------------- RESTART & START/ZAKOŃCZ --------------------
    btn_row = st.columns(2)

    # Czy wszyscy aktywni gracze są gotowi (po START)?
    other_players = [n for n in players.keys() if n != nickname]
    all_ready = (
        len(players) >= 2
        and all(p["ready"] for p in players.values())
    )

    # RESTART – resetuje grę w pokoju + Twoje plansze
    with btn_row[0]:
        if st.button("RESTART", key="restart_btn"):
            # Reset Twoich plansz
            st.session_state.boards = make_empty_boards()
            st.session_state.current_board = "zielona"

            # Reset stanu gry w pokoju
            room_data["game_over"] = False
            room_data["winner"] = None
            for p in players.values():
                p["ready"] = False
                p["green_locked"] = None

            room_data["chat"].append({
                "author": "SYSTEM",
                "text": f"{nickname} zresetował grę.",
            })
            st.experimental_rerun()

    # START / ZAKOŃCZ
    with btn_row[1]:
        if room_data["game_over"]:
            st.button("Gra zakończona", disabled=True, key="game_over_btn")
        else:
            # START – jeśli jeszcze nie gotowy
            if not player_entry["ready"]:
                if st.button("START", key="start_btn"):
                    # Sprawdzamy Twoją zieloną planszę
                    my_green = boards["zielona"]
                    valid, msg = check_layout(my_green)
                    my_green["layout_valid"] = valid
                    my_green["layout_msg"] = msg

                    if not valid:
                        st.error(msg)
                    else:
                        # Zapisujemy zamrożoną wersję Twojej zielonej planszy
                        player_entry["ready"] = True
                        player_entry["green_locked"] = dict(my_green)
                        room_data["chat"].append({
                            "author": "SYSTEM",
                            "text": f"{nickname} zakończył ustawianie swojej planszy.",
                        })
                        st.experimental_rerun()
            else:
                # Już kliknąłeś START
                label = "ZAKOŃCZ"
                disabled = not all_ready
                help_text = None
                if not all_ready:
                    help_text = "Czekaj, aż przeciwnik też kliknie START."

                if st.button(label, key="finish_btn", disabled=disabled):
                    # Koniec gry – porównujemy Twoją fioletową z zieloną przeciwnika
                    if not other_players:
                        room_data["chat"].append({
                            "author": "SYSTEM",
                            "text": "Nie ma przeciwnika w pokoju – nie można zakończyć gry.",
                        })
                    else:
                        opp_name = sorted(other_players)[0]
                        opp_entry = players[opp_name]
                        true_board = opp_entry.get("green_locked")

                        if true_board is None:
                            room_data["chat"].append({
                                "author": "SYSTEM",
                                "text": f"Przeciwnik {opp_name} nie zatwierdził jeszcze swojej planszy.",
                            })
                        else:
                            guess_board = boards["fioletowa"]
                            if boards_equal(guess_board, true_board):
                                winner = nickname
                            else:
                                winner = opp_name

                            room_data["game_over"] = True
                            room_data["winner"] = winner
                            room_data["chat"].append({
                                "author": "SYSTEM",
                                "text": f"Gra zakończona. Wygrał {winner}. (Zakończył {nickname}.)",
                            })
                            st.experimental_rerun()

                if help_text and not disabled:
                    st.caption(help_text)
                elif help_text and disabled:
                    st.caption(help_text)
