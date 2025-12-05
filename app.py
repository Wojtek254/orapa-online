import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import string
from shapely.geometry import Polygon

# ---------------------------------------------------------
# Konfiguracja plansz (dwa światy)
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
# Funkcja tworząca "puste" plansze (dla nowej gry/pokoju)
# ---------------------------------------------------------
def make_empty_boards():
    boards = {}
    for key in BOARD_CONFIGS.keys():
        boards[key] = {
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
    return boards


# ---------------------------------------------------------
# Globalny "magazyn" pokoi (wspólny dla wszystkich sesji)
# ---------------------------------------------------------
@st.cache_resource
def get_rooms():
    """
    Zwraca globalny słownik pokoi.
    Klucz: room_code (str), wartość: {"boards": ...}.
    """
    return {}


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
# LOBBY – wybór pokoju
# ---------------------------------------------------------
rooms = get_rooms()

if "room_code" not in st.session_state:
    st.session_state.room_code = ""

room_col1, room_col2 = st.columns([1.0, 0.3])

with room_col1:
    room_input = st.text_input(
        "Kod pokoju (umów się z drugim graczem, np. ABC123)",
        value=st.session_state.room_code,
    )

with room_col2:
    st.markdown("&nbsp;")
    join_clicked = st.button("Dołącz / utwórz pokój")

if join_clicked:
    st.session_state.room_code = room_input.strip()

room_code = st.session_state.room_code.strip()

if not room_code:
    st.warning("Podaj kod pokoju, żeby zacząć grę.")
    st.stop()

# Inicjalizacja stanu gry dla tego pokoju
if room_code not in rooms:
    rooms[room_code] = {
        "boards": make_empty_boards()
    }

# Aktualna plansza (zielona/fioletowa) w ramach sesji
if "current_board" not in st.session_state:
    st.session_state.current_board = "zielona"


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
# Poligony i sprawdzanie ułożenia (dla JEDNEJ gry/state)
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
    fig, ax = plt.subplots(figsize=(7, 6))

    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)

    ax.set_xlim(-0.5, COLS + 0.5)
    ax.set_ylim(-0.5, ROWS + 0.5)

    # Siatka
    for x in range(COLS + 1):
        ax.plot([x, x], [0, ROWS], color="white", linewidth=1, zorder=0)
    for y in range(ROWS + 1):
        ax.plot([0, COLS], [y, y], color="white", linewidth=1, zorder=0)

    def row_y(r):
        return ROWS - 0.5 - r

    # Podpisy
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
# Layout: dwie kolumny sterowania + plansza + przełącznik
# ---------------------------------------------------------
controls_col1, controls_col2, board_col, switch_col = st.columns([0.4, 0.4, 2.0, 0.4])

# Przycisk przełączania planszy w prawej, wąskiej kolumnie
with switch_col:
    st.markdown("&nbsp;")
    if st.button("Przełącz planszę", key="switch_board"):
        if st.session_state.current_board == "zielona":
            st.session_state.current_board = "fioletowa"
        else:
            st.session_state.current_board = "zielona"

# Po ewentualnym przełączeniu – aktualna plansza, kolor tła, stan
board_key = st.session_state.current_board
BG_COLOR = BOARD_CONFIGS[board_key]["bg"]
state = rooms[room_code]["boards"][board_key]


# =====================================================================
#                   KOLUMNA STEROWANIA 1
# =====================================================================
with controls_col1:

    # ---------------- Żółty trójkąt ----------------
    figure_header(controls_col1, "Żółty trójkąt", "#ffd000")

    row_y1 = st.columns(3)
    if row_y1[0].button(f"{Y_ICON}⟲", key="y_rot_left"):
        state["y_ori"] = (state["y_ori"] + 1) % 4
    if row_y1[1].button(f"{Y_ICON}⬆️", key="y_up"):
        state["y_cy"] += 1
    if row_y1[2].button(f"{Y_ICON}⟳", key="y_rot_right"):
        state["y_ori"] = (state["y_ori"] - 1) % 4

    row_y2 = st.columns(3)
    if row_y2[0].button(f"{Y_ICON}⬅️", key="y_left"):
        state["y_cx"] -= 1
    if row_y2[1].button(f"{Y_ICON}⬇️", key="y_down"):
        state["y_cy"] -= 1
    if row_y2[2].button(f"{Y_ICON}➡️", key="y_right"):
        state["y_cx"] += 1

    state["y_cx"], state["y_cy"] = clamp_center(
        state["y_cx"], state["y_cy"],
        state["y_ori"], yellow_vertices
    )

    st.markdown("---")

    # ---------------- Biały trójkąt ----------------
    figure_header(controls_col1, "Biały trójkąt", "#ffffff", black_override=True)

    row_w1 = st.columns(3)
    if row_w1[0].button(f"{W_ICON}⟲", key="w_rot_left"):
        state["w_ori"] = (state["w_ori"] + 1) % 4
    if row_w1[1].button(f"{W_ICON}⬆️", key="w_up"):
        state["w_cy"] += 1
    if row_w1[2].button(f"{W_ICON}⟳", key="w_rot_right"):
        state["w_ori"] = (state["w_ori"] - 1) % 4

    row_w2 = st.columns(3)
    if row_w2[0].button(f"{W_ICON}⬅️", key="w_left"):
        state["w_cx"] -= 1
    if row_w2[1].button(f"{W_ICON}⬇️", key="w_down"):
        state["w_cy"] -= 1
    if row_w2[2].button(f"{W_ICON}➡️", key="w_right"):
        state["w_cx"] += 1

    state["w_cx"], state["w_cy"] = clamp_center(
        state["w_cx"], state["w_cy"],
        state["w_ori"], small_tri_vertices
    )

    st.markdown("---")

    # ---------------- Niebieski trójkąt ----------------
    figure_header(controls_col1, "Niebieski trójkąt", "#3399ff")

    row_b1 = st.columns(3)
    if row_b1[0].button(f"{B_ICON}⟲", key="b_rot_left"):
        state["b_ori"] = (state["b_ori"] + 1) % 4
    if row_b1[1].button(f"{B_ICON}⬆️", key="b_up"):
        state["b_cy"] += 1
    if row_b1[2].button(f"{B_ICON}⟳", key="b_rot_right"):
        state["b_ori"] = (state["b_ori"] - 1) % 4

    row_b2 = st.columns(3)
    if row_b2[0].button(f"{B_ICON}⬅️", key="b_left"):
        state["b_cx"] -= 1
    if row_b2[1].button(f"{B_ICON}⬇️", key="b_down"):
        state["b_cy"] -= 1
    if row_b2[2].button(f"{B_ICON}➡️", key="b_right"):
        state["b_cx"] += 1

    state["b_cx"], state["b_cy"] = clamp_center(
        state["b_cx"], state["b_cy"],
        state["b_ori"], small_tri_vertices
    )

    st.markdown("---")

    # ---------------- Jasnoniebieski kwadrat ----------------
    figure_header(controls_col1, "Jasnoniebieski kwadrat", "#66c2ff")

    row_lb1 = st.columns(3)
    if row_lb1[1].button(f"{B_ICON}⬆️", key="lb_up"):
        state["lb_y"] += 1

    row_lb2 = st.columns(3)
    if row_lb2[0].button(f"{B_ICON}⬅️", key="lb_left"):
        state["lb_x"] -= 1
    if row_lb2[1].button(f"{B_ICON}⬇️", key="lb_down"):
        state["lb_y"] -= 1
    if row_lb2[2].button(f"{B_ICON}➡️", key="lb_right"):
        state["lb_x"] += 1

    state["lb_x"], state["lb_y"] = clamp_lightblue(
        state["lb_x"], state["lb_y"]
    )


# =====================================================================
#                   KOLUMNA STEROWANIA 2
# =====================================================================
with controls_col2:

    # ---------------- Biały kwadrat ----------------
    figure_header(controls_col2, "Biały kwadrat", "#ffffff", black_override=True)

    row_s1 = st.columns(3)
    if row_s1[1].button(f"{W_ICON}⬆️", key="s_up"):
        state["s_cy"] += 1

    row_s2 = st.columns(3)
    if row_s2[0].button(f"{W_ICON}⬅️", key="s_left"):
        state["s_cx"] -= 1
    if row_s2[1].button(f"{W_ICON}⬇️", key="s_down"):
        state["s_cy"] -= 1
    if row_s2[2].button(f"{W_ICON}➡️", key="s_right"):
        state["s_cx"] += 1

    state["s_cx"], state["s_cy"] = clamp_center(
        state["s_cx"], state["s_cy"],
        state["s_ori"], square_diamond_vertices
    )

    st.markdown("---")

    # ---------------- Czerwony równoległobok ----------------
    figure_header(controls_col2, "Czerwony równoległobok", "#ff3333")

    row_r1 = st.columns(4)
    if row_r1[0].button(f"{R_ICON}⟲", key="r_rot_left"):
        state["r_ori"] = (state["r_ori"] + 1) % 4
    if row_r1[1].button(f"{R_ICON}⬆️", key="r_up"):
        state["r_cy"] += 1
    if row_r1[2].button(f"{R_ICON}⟳", key="r_rot_right"):
        state["r_ori"] = (state["r_ori"] - 1) % 4
    if row_r1[3].button(f"{R_ICON}🔁", key="r_flip_btn"):
        state["r_flip"] = not state["r_flip"]

    row_r2 = st.columns(3)
    if row_r2[0].button(f"{R_ICON}⬅️", key="r_left"):
        state["r_cx"] -= 1
    if row_r2[1].button(f"{R_ICON}⬇️", key="r_down"):
        state["r_cy"] -= 1
    if row_r2[2].button(f"{R_ICON}➡️", key="r_right"):
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
    if row_t2_1[0].button(f"{W_ICON}⟲", key="t2_rot_left"):
        state["t2_ori"] = (state["t2_ori"] + 1) % 4
    if row_t2_1[1].button(f"{W_ICON}⬆️", key="t2_up"):
        state["t2_cy"] += 1
    if row_t2_1[2].button(f"{W_ICON}⟳", key="t2_rot_right"):
        state["t2_ori"] = (state["t2_ori"] - 1) % 4

    row_t2_2 = st.columns(3)
    if row_t2_2[0].button(f"{W_ICON}⬅️", key="t2_left"):
        state["t2_cx"] -= 1
    if row_t2_2[1].button(f"{W_ICON}⬇️", key="t2_down"):
        state["t2_cy"] -= 1
    if row_t2_2[2].button(f"{W_ICON}➡️", key="t2_right"):
        state["t2_cx"] += 1

    state["t2_cx"], state["t2_cy"] = clamp_center(
        state["t2_cx"], state["t2_cy"],
        state["t2_ori"], tri_hyp2_vertices
    )

    st.markdown("---")

    # ---------------- PRZYCISK SPRAWDZANIA UKŁADU ----------------
    figure_header(controls_col2, "Sprawdzenie ułożenia", "#ffffff", black_override=True)

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
# Plansza – prawa duża kolumna
# ---------------------------------------------------------
with board_col:
    board_title = BOARD_CONFIGS[board_key]["label"]
    st.markdown(
        f"<h2 style='text-align:center; margin-top:0;'>{board_title}</h2>",
        unsafe_allow_html=True,
    )
    fig = draw_board(state, BG_COLOR)
    st.pyplot(fig)
