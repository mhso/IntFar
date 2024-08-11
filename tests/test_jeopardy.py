from unittest import TestCase
from io import BytesIO
from PIL import Image
from multiprocessing import Process
from random import Random
from time import sleep
import os
from playwright.sync_api import sync_playwright, Playwright, BrowserContext, Page, Dialog
from urllib.parse import urlencode, quote_plus
from threading import Thread, Barrier, Event

from src.run_flask import run_app
from src.app.util import get_hashed_secret
from src.api.config import Config
from src.api.meta_database import MetaDatabase
from src.discbot.commands.util import ADMIN_DISC_ID

BROWSER_OPTIONS = {
    "args": [
        "--disable-gl-drawing-for-tests",
        "--hide-scrollbars",
            "--in-process-gpu",
        "--disable-gpu",
        "--no-sandbox",
        "--headless=new",
    ],
    "ignore_default_args": [
        "--enable-automation"
    ],
    "chromium_sandbox": False,
    "headless": True
}

BASE_URL = "http://localhost:5000/intfar/jeopardy"
JEOPARDY_PRESENTER_URL = f"{BASE_URL}/presenter"

PRESENTER_VIEWPORT = {"width": 1920, "height": 1080}
CONTESTANT_VIEWPORT = {"width": 428, "height": 926}
PRESENTER_ACTION_KEY = "NumLock"
CONTESTANT_IDS = [
    115142485579137029,
    172757468814770176,
    331082926475182081,
    347489125877809155
]
BARRIER = Barrier(len(CONTESTANT_IDS))

def _normalize_url(url):
    return url if not url.endswith("/") else url[:-1]

def _get_players_query_string(turn_id, question_num, player_data):
    query_params = {}
    for index, (disc_id, score, name, color) in enumerate(player_data, start=1):
        query_params[f"i{index}"] = disc_id
        query_params[f"s{index}"] = score
        query_params[f"n{index}"] = name
        query_params[f"c{index}"] = color

    return (
        f"{urlencode(query_params, quote_via=quote_plus)}"
        f"&turn={turn_id}&question={question_num}"
    )

class ContextHandler:
    def __init__(self, player_names={}, setup_callback=None):
        self.config = Config()
        self.playwright_contexts = []
        self.flask_process = None
        self.presenter_context = None
        self.presenter_page = None
        self.contestant_contexts = []
        self.contestant_pages = []
        self._browser_threads = []
        self._player_names = player_names
        self._setup_callback = setup_callback
        self._setup_event = Event()
        self._close_event = Event()

    def _create_browser(self, context: Playwright):
        return context.chromium.launch(**BROWSER_OPTIONS)

    def _open_presenter_lobby_page(self):
        page = self.presenter_context.new_page()
        page.goto(JEOPARDY_PRESENTER_URL)

        return page

    def _open_contestant_lobby_page(self, context: BrowserContext, disc_id: int, page: Page = None):
        client_secret = MetaDatabase(self.config).get_client_secret(disc_id)
        url = f"{BASE_URL}/{client_secret}"

        if page is None:
            page = context.new_page()

        page.goto(url)

        return page

    def _join_lobby(self, disc_id: int, page: Page):
        name = self._player_names.get(disc_id)
        if name is not None:
            # Input player name
            name_input = page.query_selector("#contestant-lobby-name")
            name_input.fill(name)

        # Join the lobby
        join_button = page.query_selector("#contestant-lobby-join")
        join_button.click()

        # Wait for the lobby page to load
        page.expect_navigation(url=f"{BASE_URL}/game")

    def _setup_contestant_browser(self, disc_id):
        if self._setup_callback:
            playwright_context = sync_playwright().__enter__()
            self.playwright_contexts.append(playwright_context)
        else:
            playwright_context = self.playwright_contexts[0]

        browser_context = self._create_browser(playwright_context).new_context(viewport=CONTESTANT_VIEWPORT, is_mobile=True, has_touch=True)
        page = self._open_contestant_lobby_page(browser_context, disc_id)
        page.on("console", lambda msg: print("Message from console:", " ".join(str(arg.json_value()) for arg in msg.args)))
        self._join_lobby(disc_id, page)

        if self._setup_callback:
            self._setup_event.set()
            try:
                self._setup_callback(page, disc_id)
                self._close_event.wait()
            except:
                playwright_context.stop()

        return browser_context, page

    def start_game(self):
        reset_questions_btn = self.presenter_page.query_selector("#menu-buttons > button")
        reset_questions_btn.click()

        self.presenter_page.press("body", PRESENTER_ACTION_KEY)

    def open_presenter_selection_page(
        self,
        round_num: int,
        question_num: int,
        turn_id: int,
        player_data: list[tuple[str, int, int, str]]
    ):
        query_str = _get_players_query_string(turn_id, question_num, player_data)
        self.presenter_page.goto(f"{JEOPARDY_PRESENTER_URL}/{round_num}?{query_str}")

    def open_presenter_question_page(
        self,
        round_num: int,
        category: str,
        difficulty: int,
        question_num: int,
        turn_id: int,
        player_data: list[tuple[str, int, int, str]]
    ):
        query_str = _get_players_query_string(turn_id, question_num, player_data)
        self.presenter_page.goto(f"{JEOPARDY_PRESENTER_URL}/{round_num}/{category}/{difficulty}?{query_str}")

    def show_question(self, is_daily_double=False):
        if not is_daily_double:
            # Show the question
            self.presenter_page.press("body", PRESENTER_ACTION_KEY)

        sleep(1)

        self.presenter_page.press("body", PRESENTER_ACTION_KEY)

        sleep(0.5)

        # Check if question is multiple choice
        is_multiple_choice = self.presenter_page.evaluate("() => document.getElementsByClassName('question-answer-entry').length > 0")
        if is_multiple_choice:
            for _ in range(4):
                self.presenter_page.press("body", PRESENTER_ACTION_KEY)
                sleep(0.5)
        else:
            self.presenter_page.press("body", PRESENTER_ACTION_KEY)

    def make_daily_double_wager(self, page: Page, amount: int, dialog_callback, is_valid):
        # Input the amount to wager
        wager_input = page.query_selector("#question-wager-input")
        wager_input.fill(str(amount))

        # Handle alert
        page.on("dialog", lambda dialog: dialog_callback(dialog, is_valid))

        # Click the submit button
        submit_button = page.query_selector("#contestant-wager-btn")
        submit_button.tap()

    def open_endscreen_page(self, player_data: list[tuple[str, int, int, str]]):
        query_str = _get_players_query_string("null", 1, player_data)
        self.presenter_page.goto(f"{JEOPARDY_PRESENTER_URL}/endscreen?{query_str}")

    def screenshot_views(self, index: int = 0):
        width = PRESENTER_VIEWPORT["width"]
        height = PRESENTER_VIEWPORT["height"] + CONTESTANT_VIEWPORT["height"]
        combined_image = Image.new("RGB", (width, height))

        presenter_sc = self.presenter_page.screenshot(type="png")
        with BytesIO(presenter_sc) as fp:
            presenter_image = Image.open(fp)
            combined_image.paste(presenter_image)

        x = (PRESENTER_VIEWPORT["width"] - CONTESTANT_VIEWPORT["width"] * 4) // 2
        y = PRESENTER_VIEWPORT["height"]
        for contestant_page in self.contestant_pages:
            contestant_sc = contestant_page.screenshot(type="png")
            with BytesIO(contestant_sc) as fp:
                contestant_image = Image.open(fp)
                combined_image.paste(contestant_image, (x, y))
                x += contestant_image.width

        combined_image.save(f"jeopardy_test_{index}.png")

    def __enter__(self):
        self.playwright_contexts = [sync_playwright().__enter__()]

        cwd = os.getcwd()
        new_cwd = os.path.join(cwd, "src")
        os.chdir(new_cwd)

        meta_database = MetaDatabase(self.config)
        self.flask_process = Process(target=run_app, args=(self.config, meta_database, {}, {}, {}, None))
        self.flask_process.start()

        os.chdir(cwd)

        # Create presenter browser and context
        client_secret = meta_database.get_client_secret(ADMIN_DISC_ID)
        hashed_secret = get_hashed_secret(client_secret)

        presenter_browser = self._create_browser(self.playwright_contexts[0])
        self.presenter_context = presenter_browser.new_context(viewport=PRESENTER_VIEWPORT)
        self.presenter_context.add_cookies([{"name": "user_id", "value": hashed_secret, "url": BASE_URL}])

        # Go to presenter URL
        self.presenter_page = self._open_presenter_lobby_page()

        # Create contestant browsers and contexts
        for disc_id in CONTESTANT_IDS:
            if self._setup_callback:
                thread = Thread(target=self._setup_contestant_browser, args=(disc_id,))
                thread.start()
                self._browser_threads.append(thread)
            else:
                context, page = self._setup_contestant_browser(disc_id)
                self.contestant_contexts.append(context)
                self.contestant_pages.append(page)

        if self._setup_callback:
            self._setup_event.wait()

        sleep(1)

        return self

    def __exit__(self, *args):
        self.playwright_contexts[0].stop()

        self._close_event.set()

        for thread in self._browser_threads:
            thread.join()

        self.flask_process.terminate()
        while self.flask_process.is_alive():
            sleep(0.1)

        self.flask_process.close()

class TestWrapper(TestCase):
    def setUp(self):
        self.random = Random(1337)

    def test_join(self):
        player_names = {
            CONTESTANT_IDS[0]: "Davido",
            CONTESTANT_IDS[1]: "Martini",
            CONTESTANT_IDS[2]: "Terning",
            CONTESTANT_IDS[3]: "Nønton"
        }

        with ContextHandler(player_names=player_names) as context:
            # Simulate a person going to the previous page
            context.contestant_pages[0].go_back()

            self.assertEqual(_normalize_url(context.presenter_page.url), JEOPARDY_PRESENTER_URL)

            for page in context.contestant_pages:
                self.assertEqual(_normalize_url(page.url), f"{BASE_URL}/game")
                status_header = page.query_selector("#contestant-game-waiting")
                self.assertNotEqual(status_header, None)
                self.assertEqual(status_header.text_content(), "Venter på at spillet starter...")

            self.assertEqual(_normalize_url(context.contestant_pages[0].url), f"{BASE_URL}/game")

            # Simulate person closing the page and re-opening it
            context._open_contestant_lobby_page(
                context.contestant_contexts[0],
                CONTESTANT_IDS[0],
                context.contestant_pages[0]
            )

            self.assertEqual(_normalize_url(context.contestant_pages[0].url), f"{BASE_URL}/game")

            name_elems = context.presenter_page.query_selector_all("#menu-contestants > .menu-contestant-id")
            expected_names = list(player_names.values())
            for index, name in enumerate(name_elems):
                self.assertEqual(expected_names[index], name.text_content())

    def test_first_turn(self):
        with ContextHandler() as context:
            # Start the game
            context.start_game()

            sleep(1)

            for page in context.contestant_pages:
                self.assertEqual(_normalize_url(page.url), f"{BASE_URL}/game")
                round_headers = page.query_selector_all(".contestant-round-header")
                turn_desc = page.query_selector("#contestant-turn-desc")
                self.assertEqual(round_headers[0].text_content(), "Runde 1/3")
                self.assertEqual(round_headers[1].text_content(), "Spørgsmål 1/30")
                self.assertEqual(turn_desc.text_content(), "")

            # Choose a player to get the first turn
            context.presenter_page.press("body", PRESENTER_ACTION_KEY)

            # Wait until player has been chosen
            context.presenter_page.wait_for_function("() => playerTurn != -1")
            player_turn = context.presenter_page.evaluate("() => playerTurn")

            for index, page in enumerate(context.contestant_pages):
                turn_desc = page.query_selector("#contestant-turn-desc")
                if index == player_turn:
                    expected_desc = "Din tur til at vælge en kategori!"
                else:
                    expected_desc = "Venter på at en anden spiller vælger en kategori..."

                self.assertEqual(expected_desc, turn_desc.text_content())

    def test_buzz_in_sequential(self):
        round_num = 1
        category = "lore"
        difficulty = 1
        question_num = 1
        turn_id = 1
        player_data = [
            (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
            (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
            (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
            (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
        ]

        with ContextHandler() as context:
            # Go to question page
            context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
            sleep(1)

            context.show_question()
            sleep(2)

            player_pings = []
            for index, page in enumerate(context.contestant_pages):
                ping_elem = page.query_selector("#contestant-game-ping")
                player_pings.append((float(ping_elem.text_content().split(" ")[0]), index))

            player_pings.sort(key=lambda x: x[0], reverse=True)

            for _, index in player_pings:
                context.contestant_pages[index].wait_for_selector("#buzzer-wrapper")

            for _, index in player_pings:
                context.contestant_pages[index].query_selector("#buzzer-wrapper").tap()

            sleep(2)

            buzzed_in_first = []
            for _, index in player_pings:
                buzz_winner_elem = context.contestant_pages[index].query_selector("#buzzer-winner")
                buzzed_first = buzz_winner_elem.evaluate("elem => !elem.classList.contains('d-none')")
                buzzed_in_first.append(buzzed_first)

            candidates = []
            prev_ping = player_pings[0][0]
            for ping, index in player_pings:
                if ping > prev_ping:
                    break

                candidates.append((ping, index))
                prev_ping = ping

            if len(candidates) == 1:
                self.assertTrue(buzzed_in_first[candidates[0][1]])
                for i in range(1, len(player_pings)):
                    self.assertFalse(buzzed_in_first[player_pings[i][1]])
            else:
                won_buzz_players = []
                for index, won in enumerate(buzzed_in_first):
                    if won:
                        won_buzz_players.append(index)

                self.assertEqual(len(won_buzz_players), 1)
                self.assertIn(won_buzz_players[0], [x[1] for x in candidates])

    def _do_buzz_in(self, page: Page, disc_id: int):
        for _ in range(10):
            try:
                page.wait_for_function("() => document.getElementById('buzzer-active') != null && !document.getElementById('buzzer-active').classList.contains('d-none')", timeout=1000)
            except Exception:
                pass

        BARRIER.wait()

        if disc_id == 347489125877809155:
            # Nø never buzzes in...
            return

        # Sleep for a random amount of time, between 0 and 10 ms
        sleep_duration = self.random.random() * 0.001
        sleep(sleep_duration)

        page.query_selector("#buzzer-wrapper").tap()

    def test_buzz_in_parallel(self):
        round_num = 1
        category = "lore"
        difficulty = 1
        question_num = 1
        turn_id = 1
        player_data = [
            (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
            (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
            (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
            (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
        ]

        with ContextHandler(setup_callback=self._do_buzz_in) as context:
            # Go to question page
            context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)

            sleep(3)

            context.show_question()

            sleep(2)

            context.presenter_page.wait_for_load_state("domcontentloaded")

            context.presenter_page.wait_for_function(
                "() => document.getElementById('question-buzz-feed').children[0].children.length == 3", timeout=15000
            )

            players_buzzed_in = context.presenter_page.eval_on_selector(
                "#question-buzz-feed", "(elem) => Array.from(elem.children[0].children).map((c) => c.textContent)"
            )

            self.assertEqual(len(players_buzzed_in), 3)

            # Verify that everyone we expected to have buzzed in, did
            people_missing_buzz_in = set(["Murt", "Dave", "Muds", "Nø"])
            for buzz_desc in players_buzzed_in:
                for name in people_missing_buzz_in:
                    if buzz_desc.startswith(f"{name} buzzede ind efter"):
                        break

                people_missing_buzz_in.remove(name)

            self.assertEqual({"Nø"}, people_missing_buzz_in)

    def test_daily_double(self):
        round_num = 1
        category = "mechanics"
        difficulty = 1
        question_num = 2
        turn_id = 2
        player_data = [
            (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
            (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
            (CONTESTANT_IDS[2], -1200, "Muds", "FF00FF"),
            (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
        ]

        with ContextHandler() as context:
            sleep(1)

            # Go to question page
            context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
            sleep(1)

            # Verify that the correct contestant can answer the daily double
            for index, page in enumerate(context.contestant_pages):
                header_text = page.query_selector("h3").text_content()
                if index == turn_id:
                    self.assertTrue(header_text.startswith("Your move! Hvor mange GBP vil du satse?"))
                else:
                    self.assertEqual(header_text, "Venter på at Muds svarer på Daily Double...")

            def dialog_callback(dialog: Dialog, is_valid: bool):
                self.assertFalse(is_valid)
                self.assertEqual(dialog.message, "Ugyldig mængde point, skal være mellem 100 og 500")
                dialog.accept()

            # Wager an amount that is too low
            context.make_daily_double_wager(context.contestant_pages[turn_id], 0, dialog_callback, False)
            sleep(0.5)

            # Wager an amount that is too hight
            context.make_daily_double_wager(context.contestant_pages[turn_id], 700, dialog_callback, False)
            sleep(0.5)

            # Wager an amount that is just right
            context.make_daily_double_wager(context.contestant_pages[turn_id], 500, dialog_callback, True)
            sleep(1)

            context.show_question(True)
            sleep(1)

            context.presenter_page.press("body", PRESENTER_ACTION_KEY)
            sleep(0.5)
            context.presenter_page.press("body", "1")
            sleep(3)

            score_text = context.presenter_page.query_selector_all(".footer-contestant-entry-score")[turn_id].text_content()
            player_score = int(score_text.split(" ")[0])
            self.assertEqual(player_score, player_data[turn_id][1] + 500)

    def test_final_jeopardy(self):
        pass

    def test_endscreen(self):
        player_data = [
            (CONTESTANT_IDS[0], 800, "Dave", "F30B0B"),
            (CONTESTANT_IDS[1], 500, "Murt", "CCCC00"),
            (CONTESTANT_IDS[2], -1200, "Muds", "FF00FF"),
            (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
        ]
        with ContextHandler() as context:
            sleep(1)

            # Go to endscreen page
            context.open_endscreen_page(player_data)
            sleep(1)

    # def test_all_questions(self):
    #     turn_id = 0
    #     player_data = [
    #         (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
    #         (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
    #         (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
    #         (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
    #     ]
    #     with ContextHandler() as context:
    #         context.presenter_page.on("requestfinished", lambda req: print("Request:", req.url))

    #         context.open_presenter_selection_page(1, 0, turn_id, player_data)
    #         context.screenshot_views(0)

    #         for round_num in range(2):
    #             question_num = 0
    #             for category in ("mechanics", "lore", "icons", "outlines", "brois", "audio"):
    #                 for difficulty in range(1, 6):
    #                     # Go to question page
    #                     context.open_presenter_question_page(round_num + 1, category, difficulty, question_num, turn_id, player_data)
    #                     sleep(1)

    #                     context.show_question()
    #                     sleep(1)

    #                     context.screenshot_views((round_num * 30) + question_num + 1)

    #                     question_num += 1
