import asyncio
import json
from typing import List
from io import BytesIO
from PIL import Image
from multiprocessing import Process
import random
import os
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page, Dialog, ConsoleMessage
from urllib.parse import urlencode, quote_plus
from threading import Barrier

import pytest

from src.run_flask import run_app
from src.app.util import get_hashed_secret
from src.api.util import MY_GUILD_ID, JEOPARDY_REGULAR_ROUNDS, JEOPADY_EDITION, JEOPARDY_ITERATION
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
PRESENTER_ACTION_KEY = "Space"
CONTESTANT_IDS = [
    115142485579137029,
    172757468814770176,
    331082926475182081,
    219497453374668815
]
BARRIER = Barrier(len(CONTESTANT_IDS))

def _normalize_url(url):
    return url if not url.endswith("/") else url[:-1]

def _get_players_query_string(turn_id, question_num, player_data):
    query_params = {}
    for index, (disc_id, score, name, color) in enumerate(player_data, start=1):
        query_params[f"i{index}"] = str(disc_id)
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
        self.presenter_context: BrowserContext = None
        self.presenter_page: Page = None
        self.contestant_contexts: List[BrowserContext] = []
        self.contestant_pages: List[Page] = []
        self._browser_tasks = []
        self._player_names = player_names
        self._setup_callback = setup_callback

    async def _create_browser(self, context: Playwright):
        return await context.chromium.launch(**BROWSER_OPTIONS)

    async def _open_presenter_lobby_page(self):
        page = await self.presenter_context.new_page()
        await page.goto(JEOPARDY_PRESENTER_URL)

        return page

    async def _open_contestant_lobby_page(self, context: BrowserContext, disc_id: int, page: Page = None):
        client_secret = MetaDatabase(self.config).get_client_secret(disc_id)
        url = f"{BASE_URL}/{client_secret}"

        if page is None:
            page = await context.new_page()

        await page.goto(url)
        return page

    async def _join_lobby(self, disc_id: int, page: Page):
        name = self._player_names.get(disc_id)
        if name is not None:
            # Input player name
            name_input = await page.query_selector("#contestant-lobby-name")
            await name_input.fill(name)

        # Join the lobby
        join_button = await page.query_selector("#contestant-lobby-join")
        await join_button.click()

        # # Wait for the lobby page to load
        # async with page.expect_navigation(url=f"{BASE_URL}/game", wait_until="domcontentloaded"):
        #     pass

    async def _print_console_output(self, msg: ConsoleMessage):
        strings = [str(await arg.json_value()) for arg in msg.args]
        print("Message from console:", " ".join(strings))

    async def _setup_contestant_browser(self, disc_id):
        if self._setup_callback:
            playwright_context = await async_playwright().__aenter__()
            self.playwright_contexts.append(playwright_context)
        else:
            playwright_context = self.playwright_contexts[0]

        browser = await self._create_browser(playwright_context)
        browser_context = await browser.new_context(viewport=CONTESTANT_VIEWPORT, is_mobile=True, has_touch=True)
        page = await self._open_contestant_lobby_page(browser_context, disc_id)
        page.on("console", self._print_console_output)
        await self._join_lobby(disc_id, page)

        if self._setup_callback:
            await self._setup_callback(disc_id, page)

        return browser_context, page

    async def start_game(self):
        reset_questions_btn = await self.presenter_page.query_selector("#menu-buttons > button")
        await reset_questions_btn.click()

        # Plays intro music
        await self.presenter_page.press("body", PRESENTER_ACTION_KEY)
        await asyncio.sleep(1.5)
        # Starts the game
        await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

    async def open_presenter_selection_page(
        self,
        round_num: int,
        question_num: int,
        turn_id: int,
        player_data: list[tuple[int, int, int, str]]
    ):
        query_str = _get_players_query_string(turn_id, question_num, player_data)
        await self.presenter_page.goto(f"{JEOPARDY_PRESENTER_URL}/{round_num}?{query_str}")

    async def open_presenter_question_page(
        self,
        round_num: int,
        category: str,
        difficulty: int,
        question_num: int,
        turn_id: int,
        player_data: list[tuple[int, int, str, str]]
    ):
        query_str = _get_players_query_string(turn_id, question_num, player_data)
        await self.presenter_page.goto(f"{JEOPARDY_PRESENTER_URL}/{round_num}/{category}/{difficulty}?{query_str}")

    async def show_question(self, is_daily_double=False):
        if not is_daily_double:
            # Show the question
            await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

        await asyncio.sleep(1)

        await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

        await asyncio.sleep(0.5)

        # Check if question is multiple choice
        is_multiple_choice = await self.presenter_page.evaluate("() => document.getElementsByClassName('question-answer-entry').length > 0")
        if is_multiple_choice:
            for _ in range(4):
                await self.presenter_page.press("body", PRESENTER_ACTION_KEY)
                await asyncio.sleep(0.5)
        else:
            await self.presenter_page.press("body", PRESENTER_ACTION_KEY)

    async def get_player_scores(self):
        point_elems = await self.presenter_page.query_selector_all(".footer-contestant-entry-score")
        points_text = [await elem.text_content() for elem in point_elems]
        points_values = await self.presenter_page.evaluate("playerScores")

        points_contestants = []
        for page in self.contestant_pages:
            elem = await page.query_selector("#contestant-game-score")
            points_contestants.append(await elem.text_content())

        return points_text, points_values, points_contestants

    async def make_daily_double_wager(self, page: Page, amount: int, dialog_callback=None):
        # Input the amount to wager
        wager_input = await page.query_selector("#question-wager-input")
        await wager_input.fill(str(amount))

        async def fail(dialog):
            assert False

        # Handle alert
        if dialog_callback is not None:
            page.on("dialog", dialog_callback)
        else:
            page.on("dialog", fail)

        # Click the submit button
        submit_button = await page.query_selector("#contestant-wager-btn")
        await submit_button.tap()

    async def open_endscreen_page(self, player_data: list[tuple[str, int, int, str]]):
        query_str = _get_players_query_string("null", 1, player_data)
        await self.presenter_page.goto(f"{JEOPARDY_PRESENTER_URL}/endscreen?{query_str}")

    async def screenshot_views(self, index: int = 0):
        width = PRESENTER_VIEWPORT["width"]
        height = PRESENTER_VIEWPORT["height"] + CONTESTANT_VIEWPORT["height"]
        combined_image = Image.new("RGB", (width, height))

        presenter_sc = await self.presenter_page.screenshot(type="png")
        with BytesIO(presenter_sc) as fp:
            presenter_image = Image.open(fp)
            combined_image.paste(presenter_image)

        x = (PRESENTER_VIEWPORT["width"] - CONTESTANT_VIEWPORT["width"] * 4) // 2
        y = PRESENTER_VIEWPORT["height"]
        for contestant_page in self.contestant_pages:
            contestant_sc = await contestant_page.screenshot(type="png")
            with BytesIO(contestant_sc) as fp:
                contestant_image = Image.open(fp)
                combined_image.paste(contestant_image, (x, y))
                x += contestant_image.width

        combined_image.save(f"jeopardy_test_{index}.png")

    async def __aenter__(self):
        self.playwright_contexts = [await async_playwright().__aenter__()]

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

        presenter_browser = await self._create_browser(self.playwright_contexts[0])
        self.presenter_context = await presenter_browser.new_context(viewport=PRESENTER_VIEWPORT)
        await self.presenter_context.add_cookies([{"name": "user_id", "value": hashed_secret, "url": BASE_URL}])

        # Go to presenter URL
        self.presenter_page = await self._open_presenter_lobby_page()

        # Create contestant browsers and contexts
        for disc_id in CONTESTANT_IDS:
            if self._setup_callback:
                task = asyncio.create_task(self._setup_contestant_browser(disc_id))
                self._browser_tasks.append(task)
            else:
                context, page = await self._setup_contestant_browser(disc_id)
                self.contestant_contexts.append(context)
                self.contestant_pages.append(page)

        await asyncio.sleep(1)

        return self

    async def __aexit__(self, *args):
        await self.playwright_contexts[0].stop()

        while any(not task.done() for task in self._browser_tasks):
            await asyncio.sleep(0.1)

        self.flask_process.terminate()
        while self.flask_process.is_alive():
            await asyncio.sleep(0.1)

        self.flask_process.close()

@pytest.mark.asyncio
async def test_join():
    player_names = {
        CONTESTANT_IDS[0]: "Davido",
        CONTESTANT_IDS[1]: "Martini",
        CONTESTANT_IDS[2]: "Terning",
        CONTESTANT_IDS[3]: "Nønton"
    }

    async with ContextHandler(player_names=player_names) as context:
        # Simulate a person going to the previous page
        await context.contestant_pages[0].go_back()

        assert _normalize_url(context.presenter_page.url) == JEOPARDY_PRESENTER_URL

        for page in context.contestant_pages:
            assert _normalize_url(page.url) == f"{BASE_URL}/game"
            status_header = await page.query_selector("#contestant-game-waiting")
            assert status_header is not None
            assert await status_header.text_content() == "Venter på at spillet starter..."

        assert _normalize_url(context.contestant_pages[0].url) == f"{BASE_URL}/game"

        # Simulate person closing the page and re-opening it
        await context._open_contestant_lobby_page(
            context.contestant_contexts[0],
            CONTESTANT_IDS[0],
            context.contestant_pages[0]
        )

        assert _normalize_url(context.contestant_pages[0].url) == f"{BASE_URL}/game"

        name_elems = await context.presenter_page.query_selector_all("#menu-contestants > .menu-contestant-id")
        expected_names = list(player_names.values())
        for index, name in enumerate(name_elems):
            assert expected_names[index] == await name.text_content()

@pytest.mark.asyncio
async def test_first_turn():
   async with ContextHandler() as context:
        # Start the game
        await context.start_game()

        await asyncio.sleep(1)

        for page in context.contestant_pages:
            assert _normalize_url(page.url) == f"{BASE_URL}/game"
            round_headers = await page.query_selector_all(".contestant-round-header")
            turn_desc = await page.query_selector("#contestant-turn-desc")
            rounds = JEOPARDY_REGULAR_ROUNDS + 1
            assert await round_headers[0].text_content() == f"Runde 1/{rounds}"
            assert await round_headers[1].text_content() == "Spørgsmål 1/30"
            assert await turn_desc.text_content() == ""

        # Choose a player to get the first turn
        await context.presenter_page.press("body", PRESENTER_ACTION_KEY)

        # Wait until player has been chosen
        await context.presenter_page.wait_for_function("() => playerTurn != -1")
        player_turn = await context.presenter_page.evaluate("() => playerTurn")

        for index, page in enumerate(context.contestant_pages):
            turn_desc = await page.query_selector("#contestant-turn-desc")
            if index == player_turn:
                expected_desc = "Din tur til at vælge en kategori!"
            else:
                expected_desc = "Venter på at en anden spiller vælger en kategori..."

            assert expected_desc == await turn_desc.text_content()

@pytest.mark.asyncio
async def test_buzz_in_correct_person():
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

    random.seed(1337)

    async with ContextHandler() as context:
        # Go to question page
        await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        await context.show_question()
        sleep_time = 1.5 + random.random() * 2
        await asyncio.sleep(sleep_time)

        buzzer = await context.contestant_pages[1].wait_for_selector("#buzzer-wrapper")
        await buzzer.tap()

        await asyncio.sleep(0.5)

        for index in range(len(player_data)):
            buzz_winner_elem = await context.contestant_pages[index].query_selector("#buzzer-winner")
            buzzed_in_first = await buzz_winner_elem.evaluate("elem => !elem.classList.contains('d-none')")
            if index == 1:
                assert buzzed_in_first, "Correct player did not buzz in"
            else:
                assert not buzzed_in_first, "Wrong player buzzed in"

@pytest.mark.asyncio
async def test_buzz_in_sequential():
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

    async with ContextHandler() as context:
        # Go to question page
        await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        await context.show_question()
        await asyncio.sleep(2)

        player_pings = []
        for index, page in enumerate(context.contestant_pages):
            ping_elem = await page.query_selector("#contestant-game-ping")
            player_pings.append((float((await ping_elem.text_content()).split(" ")[0]), index))

        player_pings.sort(key=lambda x: x[0], reverse=True)

        for _, index in player_pings:
            await context.contestant_pages[index].wait_for_selector("#buzzer-wrapper")

        for _, index in player_pings:
            buzzer = await context.contestant_pages[index].query_selector("#buzzer-wrapper")
            await buzzer.tap()

        await asyncio.sleep(2)

        buzzed_in_first = []
        for _, index in player_pings:
            buzz_winner_elem = await context.contestant_pages[index].query_selector("#buzzer-winner")
            buzzed_first = await buzz_winner_elem.evaluate("elem => !elem.classList.contains('d-none')")
            buzzed_in_first.append(buzzed_first)

        candidates = []
        prev_ping = player_pings[0][0]
        for ping, index in player_pings:
            if ping > prev_ping:
                break

            candidates.append((ping, index))
            prev_ping = ping

        if len(candidates) == 1:
            assert buzzed_in_first[candidates[0][1]]
            for i in range(1, len(player_pings)):
                assert buzzed_in_first[player_pings[i][1]]
        else:
            won_buzz_players = []
            for index, won in enumerate(buzzed_in_first):
                if won:
                    won_buzz_players.append(index)

            assert len(won_buzz_players) == 1
            assert won_buzz_players[0] in [x[1] for x in candidates]

async def _do_buzz_in(disc_id: int, page: Page):
    for _ in range(10):
        try:
            await page.wait_for_function("() => document.getElementById('buzzer-active') != null && !document.getElementById('buzzer-active').classList.contains('d-none')", timeout=1000)
        except Exception:
            pass

    BARRIER.wait()

    if disc_id == 347489125877809155:
        # Nø never buzzes in...
        return

    # Sleep for a random amount of time, between 0 and 10 ms
    sleep_duration = random.random() * 0.001
    await asyncio.sleep(sleep_duration)

    buzzer = await page.query_selector("#buzzer-wrapper")
    await buzzer.tap()

# @pytest.mark.asyncio
# async def test_buzz_in_parallel():
#     round_num = 1
#     category = "lore"
#     difficulty = 1
#     question_num = 1
#     turn_id = 1
#     player_data = [
#         (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
#         (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
#         (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
#         (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
#     ]

#     random.seed(1337)

#     async with ContextHandler(setup_callback=_do_buzz_in) as context:
#         # Go to question page
#         await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
#         await asyncio.sleep(3)

#         await context.show_question()
#         await asyncio.sleep(2)

#         await context.presenter_page.wait_for_load_state("domcontentloaded")

#         await context.presenter_page.wait_for_function(
#             "() => document.getElementById('question-buzz-feed').children[0].children.length == 3", timeout=15000
#         )

#         players_buzzed_in = await context.presenter_page.eval_on_selector(
#             "#question-buzz-feed", "(elem) => Array.from(elem.children[0].children).map((c) => c.textContent)"
#         )

#         assert len(players_buzzed_in) == 3

#         # Verify that everyone we expected to have buzzed in, did
#         people_missing_buzz_in = set(["Murt", "Dave", "Muds", "Nø"])
#         for buzz_desc in players_buzzed_in:
#             for name in people_missing_buzz_in:
#                 if buzz_desc.startswith(f"{name} buzzede ind efter"):
#                     break

#             people_missing_buzz_in.remove(name)

#         assert {"Nø"} == people_missing_buzz_in

def _get_daily_double_question(config):
    filename = f"{config.static_folder}/data/jeopardy_used.json"
    with open(filename, "r", encoding="utf-8") as fp:
        data = json.load(fp)
        for category in data:
            for index, question in enumerate(data[category]):
                if question["double"]:
                    return category, (index + 1)

    data["icons"][0]["double"] = True
    with open(filename, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=4)

    return "icons", 1

@pytest.mark.asyncio
async def test_daily_double_low_score(config):
    round_num = 1
    category, difficulty = _get_daily_double_question(config)
    question_num = 2
    turn_id = 2
    player_data = [
        (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], -1200, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
    ]

    async with ContextHandler() as context:
        await asyncio.sleep(1)

        # Go to question page
        await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        # Verify that the correct contestant can answer the daily double
        for index, page in enumerate(context.contestant_pages):
            header_text = await (await page.query_selector("h3")).text_content()
            if index == turn_id:
                assert header_text.startswith("Your move! Hvor mange GBP vil du satse?")
            else:
                assert header_text, "Venter på at Muds svarer på Daily Double..."

        async def dialog_callback(dialog: Dialog):
            assert dialog.message == "Ugyldig mængde point, skal være mellem 100 og 500"
            await dialog.accept()

        # Wager an amount that is too low
        await context.make_daily_double_wager(context.contestant_pages[turn_id], 0, dialog_callback)
        await asyncio.sleep(0.5)

        # Wager an amount that is too hight
        await context.make_daily_double_wager(context.contestant_pages[turn_id], 600, dialog_callback)
        await asyncio.sleep(0.5)

        # Wager an amount that is just right
        await context.make_daily_double_wager(context.contestant_pages[turn_id], 500)
        await asyncio.sleep(1)

        await context.show_question(True)
        await asyncio.sleep(1)

        await context.presenter_page.press("body", PRESENTER_ACTION_KEY)
        await asyncio.sleep(0.5)
        await context.presenter_page.press("body", "1")
        await asyncio.sleep(3)

        scores = await context.presenter_page.query_selector_all(".footer-contestant-entry-score")
        score_text = await scores[turn_id].text_content()
        player_score = int(score_text.split(" ")[0])
        assert player_score == player_data[turn_id][1] + 500

@pytest.mark.asyncio
async def test_daily_double_high_score(config):
    round_num = 1
    category, difficulty = _get_daily_double_question(config)
    question_num = 2
    turn_id = 2
    player_data = [
        (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], 1200, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
    ]

    async with ContextHandler() as context:
        await asyncio.sleep(1)

        # Go to question page
        await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        # Verify that the correct contestant can answer the daily double
        for index, page in enumerate(context.contestant_pages):
            header_text = await (await page.query_selector("h3")).text_content()
            if index == turn_id:
                assert header_text.startswith("Your move! Hvor mange GBP vil du satse?")
            else:
                assert header_text, "Venter på at Muds svarer på Daily Double..."

        async def dialog_callback(dialog: Dialog):
            assert dialog.message == "Ugyldig mængde point, skal være mellem 100 og 1200"
            await dialog.accept()

        # Wager an amount that is too low
        await context.make_daily_double_wager(context.contestant_pages[turn_id], 0, dialog_callback)
        await asyncio.sleep(0.5)

        # Wager an amount that is too hight
        await context.make_daily_double_wager(context.contestant_pages[turn_id], 1300, dialog_callback)
        await asyncio.sleep(0.5)

        # Wager an amount that is just right
        await context.make_daily_double_wager(context.contestant_pages[turn_id], 1100)
        await asyncio.sleep(1)

        await context.show_question(True)
        await asyncio.sleep(1)

        await context.presenter_page.press("body", PRESENTER_ACTION_KEY)
        await asyncio.sleep(0.5)
        await context.presenter_page.press("body", "1")
        await asyncio.sleep(3)

        scores = await context.presenter_page.query_selector_all(".footer-contestant-entry-score")
        score_text = await scores[turn_id].text_content()
        player_score = int(score_text.split(" ")[0])
        assert player_score == player_data[turn_id][1] + 1100

@pytest.mark.asyncio
async def test_final_jeopardy():
    round_num = JEOPARDY_REGULAR_ROUNDS
    question_num = 30
    turn_id = 0
    player_data = [
        (CONTESTANT_IDS[0], 500, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], -500, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 1500, "Nø", "00FFFF")
    ]

    async with ContextHandler() as context:
        # Go to question page
        await context.open_presenter_selection_page(round_num, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        # Verify that we are on the correct page
        for page in context.contestant_pages:
            headers = await page.query_selector_all(".contestant-round-header")
            rounds = JEOPARDY_REGULAR_ROUNDS + 1
            assert await headers[0].text_content() == f"Runde {rounds}/{rounds}"
            assert await headers[1].text_content() == "Final Jeopardy!"

@pytest.mark.asyncio
async def test_endscreen():
    player_data = [
        (CONTESTANT_IDS[0], 800, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 500, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], -1200, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
    ]
    async with ContextHandler() as context:
        await asyncio.sleep(1)

        # Go to endscreen page
        await context.open_endscreen_page(player_data)
        await asyncio.sleep(1)

        header = await context.presenter_page.query_selector("#endscreen-winner-desc")
        assert (await header.text_content()).strip() == "Dave wonnered!!! All hail the king!"

async def _wait_for_event(callback, condition=None, attemps=10):
    for _ in range(attemps):
        result = await callback()
        if (condition is None and result) or (condition is not None and result == condition):
            return

        await asyncio.sleep(1)

    raise TimeoutError("Event never happened!")

async def _assert_scores(
    points_text: List[str],
    points_values: List[int],
    points_contestants: List[str],
    expected_points: List[int],
    assert_contestants: bool = False
):
    expected_text = [f"{points} GBP" for points in expected_points]

    assert points_values == expected_points
    assert points_text == expected_text
    if assert_contestants:
        assert points_contestants == expected_text

@pytest.mark.asyncio
async def test_freeze():
    round_num = 1
    category = "lore"
    difficulty = 1
    question_num = 1
    turn_id = 1
    player_data = [
        (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 0, "ThommyZalami", "00FFFF")
    ]
    power_ids = ["hijack", "freeze", "rewind"]

    async with ContextHandler() as context:
        await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        await context.show_question()

        contestant_page = context.contestant_pages[2]
        power_up_buttons = {power_id: await contestant_page.wait_for_selector(f"#contestant-power-btn-{power_id}") for power_id in power_ids}

        async def callback_hijack():
            return await power_up_buttons["hijack"].is_enabled()

        await _wait_for_event(callback_hijack)

        # Assert that only the 'hijack' power-up is available to use
        enabled_powers = {power_up: await power_up_buttons[power_up].is_enabled() for power_up in power_up_buttons}
        assert enabled_powers == {"hijack": True, "freeze": False, "rewind": False}

        # Someone buzzes in
        buzzer = await contestant_page.query_selector("#buzzer-wrapper")
        await buzzer.tap()

        buzz_winner_elem = await contestant_page.query_selector("#buzzer-winner")
        await buzz_winner_elem.wait_for_element_state("visible")

        async def callback_freeze():
            return await power_up_buttons["freeze"].is_enabled()

        await _wait_for_event(callback_freeze)

        # Assert that the 'freeze' power-up is now available to use
        enabled_powers = {power_up: await power_up_buttons[power_up].is_enabled() for power_up in power_up_buttons}
        assert enabled_powers == {"hijack": True, "freeze": True, "rewind": False}

        countdown_elem = await context.presenter_page.query_selector("#question-countdown-wrapper")
        visible = await countdown_elem.is_visible()
        assert visible, "Countdown is visible after buzz"

        # Person uses 'freeze' power-up to freeze countdown
        power_up = await contestant_page.query_selector("#contestant-power-btn-freeze")
        await power_up.tap()

        countdown_paused = await context.presenter_page.evaluate("countdownPaused")
        assert countdown_paused, "Countdown is paused after freeze"

async def _wait_for_power_up_video(context: ContextHandler):
    splash_wrapper = await context.presenter_page.wait_for_selector("#question-power-up-splash")

    async def callback_video_started():
        return await splash_wrapper.eval_on_selector("video", "(video) => video.currentTime > 0")

    await _wait_for_event(callback_video_started)

    async def callback_video_ended():
        return await splash_wrapper.eval_on_selector("video", "(video) => video.ended")

    await _wait_for_event(callback_video_ended)

@pytest.mark.asyncio
async def test_rewind_simple():
    round_num = 1
    category = "outlines"
    difficulty = 1
    question_num = 1
    turn_id = 1
    player_data = [
        (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
    ]
    power_ids = ["hijack", "freeze", "rewind"]

    async with ContextHandler() as context:
        await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        await context.show_question()

        contestant_page = context.contestant_pages[2]
        power_up_buttons = {power_id: await contestant_page.wait_for_selector(f"#contestant-power-btn-{power_id}") for power_id in power_ids}

        async def callback_hijack():
            return await power_up_buttons["hijack"].is_enabled()

        await _wait_for_event(callback_hijack)

        # Assert that only the 'hijack' power-up is available to use
        enabled_powers = {power_up: await power_up_buttons[power_up].is_enabled() for power_up in power_up_buttons}
        assert enabled_powers == {"hijack": True, "freeze": False, "rewind": False}

        # Player buzzes in
        buzzer = await contestant_page.query_selector("#buzzer-wrapper")
        await buzzer.tap()

        buzz_winner_elem = await contestant_page.query_selector("#buzzer-winner")
        await buzz_winner_elem.wait_for_element_state("visible")

        await asyncio.sleep(1)

        # Assert that the 'freeze' power-up is now available to use
        enabled_powers = {power_up: await power_up_buttons[power_up].is_enabled() for power_up in power_up_buttons}
        assert enabled_powers == {"hijack": True, "freeze": True, "rewind": False}

        # Assert that player 2 now has the turn
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [False, False, True, False]

        # Answer the question wrong
        await context.presenter_page.press("body", "Space")
        await asyncio.sleep(0.5)
        await context.presenter_page.press("body", "2")

        async def callback_rewind():
            return await power_up_buttons["rewind"].is_enabled()

        await _wait_for_event(callback_rewind)

        # Assert that the player lost points
        player_scores = await context.get_player_scores()
        await _assert_scores(*player_scores, [0, 0, -100, 0])

        # Assert that the 'rewind' power-up is now available to use
        enabled_powers = {power_up: await power_up_buttons[power_up].is_enabled() for power_up in power_up_buttons}
        assert enabled_powers == {"hijack": False, "freeze": False, "rewind": True}

        # Assert that no one has the turn now
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [False, False, False, False]

        # Person uses 'rewind' power-up to rewind and answer again
        power_up = await contestant_page.query_selector("#contestant-power-btn-rewind")
        await power_up.tap()

        await _wait_for_power_up_video(context)

        await asyncio.sleep(1)

        # Assert that player 2 has the turn again
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [False, False, True, False]

        # Assert that the player was refunded the lost points
        player_scores = await context.get_player_scores()
        await _assert_scores(*player_scores, [0, 0, 0, 0])

        # Answer the question correctly this time
        await context.presenter_page.press("body", "Space")
        await asyncio.sleep(0.5)
        await context.presenter_page.press("body", "1")

        await asyncio.sleep(0.5)

        # Assert that the player gained points
        point_elems = await context.presenter_page.query_selector_all(".footer-contestant-entry-score")
        points_text = await point_elems[2].text_content()
        points = await context.presenter_page.evaluate("playerScores[2]")

        assert points_text == "100 GBP"
        assert points == 100

@pytest.mark.asyncio
async def test_rewind_complex():
    round_num = 1
    category = "outlines"
    difficulty = 1
    question_num = 1
    turn_id = 1
    player_data = [
        (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
    ]
    power_ids = ["hijack", "freeze", "rewind"]

    async with ContextHandler() as context:
        await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        await context.show_question()

        contestant_page_1 = context.contestant_pages[0]
        contestant_page_2 = context.contestant_pages[1]
        power_up_buttons_1 = {power_id: await contestant_page_1.wait_for_selector(f"#contestant-power-btn-{power_id}") for power_id in power_ids}
        power_up_buttons_2 = {power_id: await contestant_page_2.wait_for_selector(f"#contestant-power-btn-{power_id}") for power_id in power_ids}

        async def callback_hijack():
            return await power_up_buttons_1["hijack"].is_enabled()

        await _wait_for_event(callback_hijack)

        # Player 1 buzzes in
        buzzer = await contestant_page_1.query_selector("#buzzer-wrapper")
        await buzzer.tap()

        buzz_winner_elem = await contestant_page_1.query_selector("#buzzer-winner")
        await buzz_winner_elem.wait_for_element_state("visible")

        await asyncio.sleep(1)

        # Assert that the 'freeze' power-up is now available to use for player 1
        enabled_powers = {power_up: await power_up_buttons_1[power_up].is_enabled() for power_up in power_up_buttons_1}
        assert enabled_powers == {"hijack": True, "freeze": True, "rewind": False}

        # Assert that player 1 now has the turn
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [True, False, False, False]

        # Answer the question wrong
        await context.presenter_page.press("body", "Space")
        await asyncio.sleep(0.5)
        await context.presenter_page.press("body", "2")

        async def callback_rewind():
            return await power_up_buttons_1["rewind"].is_enabled()

        await _wait_for_event(callback_rewind)

        # Assert that the player lost points
        player_scores = await context.get_player_scores()
        await _assert_scores(*player_scores, [-100, 0, 0, 0])

        # Assert that the 'rewind' power-up is now available to use
        enabled_powers = {power_up: await power_up_buttons_1[power_up].is_enabled() for power_up in power_up_buttons_1}
        assert enabled_powers == {"hijack": False, "freeze": False, "rewind": True}

        # Assert that no one has the turn now
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [False, False, False, False]

        # Player 2 buzzes in
        buzzer = await contestant_page_2.query_selector("#buzzer-wrapper")
        await buzzer.tap()

        buzz_winner_elem = await contestant_page_2.query_selector("#buzzer-winner")
        await buzz_winner_elem.wait_for_element_state("visible")

        await asyncio.sleep(1)

        # Assert that the 'freeze' power-up is now available to use for player 2
        enabled_powers = {power_up: await power_up_buttons_2[power_up].is_enabled() for power_up in power_up_buttons_2}
        assert enabled_powers == {"hijack": False, "freeze": True, "rewind": False}

        # Assert that player 2 now has the turn
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [False, True, False, False]

        # Player 1 uses 'rewind' power-up to rewind and answer again
        power_up = await contestant_page_1.query_selector("#contestant-power-btn-rewind")
        await power_up.tap()

        await _wait_for_power_up_video(context)
        await asyncio.sleep(1)

        # Assert that player 1 has the turn again
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [True, False, False, False]

        # Assert that the player was refunded the lost points
        player_scores = await context.get_player_scores()
        await _assert_scores(*player_scores, [0, 0, 0, 0])

        # Answer the question correctly this time
        await context.presenter_page.press("body", "Space")
        await asyncio.sleep(0.5)
        await context.presenter_page.press("body", "1")

        await asyncio.sleep(0.5)

        # Assert that the player gained points
        player_scores = await context.get_player_scores()
        await _assert_scores(*player_scores, [100, 0, 0, 0])

@pytest.mark.asyncio
async def test_powers_contest():
    round_num = 1
    category = "outlines"
    difficulty = 1
    question_num = 1
    turn_id = 1
    player_data = [
        (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
    ]
    power_ids = ["hijack", "freeze", "rewind"]

    async with ContextHandler() as context:
        await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        await context.show_question()

        contestant_page_1 = context.contestant_pages[0]
        contestant_page_2 = context.contestant_pages[1]
        power_up_buttons_1 = {power_id: await contestant_page_1.wait_for_selector(f"#contestant-power-btn-{power_id}") for power_id in power_ids}
        power_up_buttons_2 = {power_id: await contestant_page_2.wait_for_selector(f"#contestant-power-btn-{power_id}") for power_id in power_ids}

        async def callback_hijack():
            return await power_up_buttons_1["hijack"].is_enabled()

        await _wait_for_event(callback_hijack)

        # Player 1 buzzes in
        buzzer = await contestant_page_1.query_selector("#buzzer-wrapper")
        await buzzer.tap()

        buzz_winner_elem = await contestant_page_1.query_selector("#buzzer-winner")
        await buzz_winner_elem.wait_for_element_state("visible")

        await asyncio.sleep(1)

        # Assert that the 'freeze' power-up is now available to use for player 1
        enabled_powers = {power_up: await power_up_buttons_1[power_up].is_enabled() for power_up in power_up_buttons_1}
        assert enabled_powers == {"hijack": True, "freeze": True, "rewind": False}

        # Assert that player 1 now has the turn
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [True, False, False, False]

        # Answer the question wrong
        await context.presenter_page.press("body", "Space")
        await asyncio.sleep(0.5)
        await context.presenter_page.press("body", "2")

        async def callback_rewind():
            return await power_up_buttons_1["rewind"].is_enabled()

        await _wait_for_event(callback_rewind)

        # Assert that the player lost points
        player_scores = await context.get_player_scores()
        await _assert_scores(*player_scores, [-100, 0, 0, 0])

        # Assert that the 'rewind' power-up is now available to use
        enabled_powers = {power_up: await power_up_buttons_1[power_up].is_enabled() for power_up in power_up_buttons_1}
        assert enabled_powers == {"hijack": False, "freeze": False, "rewind": True}

        # Assert that no one has the turn now
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [False, False, False, False]

        # Player 2 buzzes in
        buzzer = await contestant_page_2.query_selector("#buzzer-wrapper")
        await buzzer.tap()

        buzz_winner_elem = await contestant_page_2.query_selector("#buzzer-winner")
        await buzz_winner_elem.wait_for_element_state("visible")

        await asyncio.sleep(1)

        # Assert that the 'freeze' power-up is now available to use for player 2
        enabled_powers = {power_up: await power_up_buttons_2[power_up].is_enabled() for power_up in power_up_buttons_2}
        assert enabled_powers == {"hijack": False, "freeze": True, "rewind": False}

        # Assert that player 2 now has the turn
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == [False, True, False, False]

        # Assert that buzz countdown is visible
        countdown_elem = await context.presenter_page.query_selector("#question-countdown-wrapper")
        visible = await countdown_elem.is_visible()
        assert visible, "Countdown is visible after buzz"

        # Player 1 uses 'rewind' power-up at almost the same time as player 2 uses 'freeze'
        rewind_power_up = await contestant_page_1.query_selector("#contestant-power-btn-rewind")
        freeze_power_up = await contestant_page_2.query_selector("#contestant-power-btn-freeze")

        try:
            task_1 = asyncio.create_task(freeze_power_up.tap(timeout=1000))
            task_2 = asyncio.create_task(rewind_power_up.tap(timeout=1000))
            await asyncio.tasks.gather(task_1, task_2)
        except TimeoutError:
            pass

        await _wait_for_power_up_video(context)

        # Ensure only one power-up use was accepted
        rewind_used = await rewind_power_up.eval_on_selector(".contestant-power-used", "img => !img.classList.contains('d-none')")
        freeze_used = await freeze_power_up.eval_on_selector(".contestant-power-used", "img => !img.classList.contains('d-none')")

        assert not (await rewind_power_up.is_enabled())
        assert not (await freeze_power_up.is_enabled())

        if rewind_used:
            assert not freeze_used

            expected_turns = [True, False, False, False]
            freeze_power_up = await contestant_page_1.query_selector("#contestant-power-btn-freeze")

            assert (await freeze_power_up.is_enabled())
        else:
            assert not rewind_used

            expected_turns = [False, True, False, False]

            countdown_elem = await context.presenter_page.query_selector("#question-countdown-wrapper")
            visible = await countdown_elem.is_visible()
            assert not visible, "Countdown is not visible after freeze"

        # Assert that expected player has the turn
        contestant_pips_active = await context.presenter_page.eval_on_selector_all(".footer-contestant-entry", "(divs) => divs.map((d) => d.classList.contains('active-contestant-entry'))")
        assert contestant_pips_active == expected_turns

@pytest.mark.asyncio
async def test_hijack_before_question():
    round_num = 1
    category = "wrong"
    difficulty = 1
    question_num = 1
    turn_id = 1
    player_data = [
        (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
    ]
    power_ids = ["hijack", "freeze", "rewind"]

    async with ContextHandler() as context:
        await context.open_presenter_question_page(round_num, category, difficulty, question_num, turn_id, player_data)
        await asyncio.sleep(1)

        await context.show_question()

        contestant_page = context.contestant_pages[0]
        power_up_buttons = {power_id: await contestant_page.wait_for_selector(f"#contestant-power-btn-{power_id}") for power_id in power_ids}

        async def callback_hijack():
            return await power_up_buttons["hijack"].is_enabled()

        await _wait_for_event(callback_hijack)

        # Use hijack power-up before question is asked
        await power_up_buttons["hijack"].tap()

        await _wait_for_power_up_video(context)

        


@pytest.mark.asyncio
async def test_discord_message_simple(discord_client):
    player_data = [
        {"disc_id": 2, "name": "Dave", "avatar": None, "score": 800, "buzzes": 4, "hits": 2, "misses": 2, "color": "F30B0B"},
        {"disc_id": 3, "name": "Murt", "avatar": None, "score": 500, "buzzes": 4, "hits": 3, "misses": 1, "color": "CCCC00"},
        {"disc_id": 4, "name": "Muds", "avatar": None, "score": -1200, "buzzes": 6, "hits": 1, "misses": 5, "color": "FF00FF"},
        {"disc_id": 5, "name": "Nø", "avatar": None, "score": -200, "buzzes": 1, "hits": 0, "misses": 1, "color": "00FFFF"},
    ]

    await discord_client.announce_jeopardy_winner(player_data, MY_GUILD_ID)

    channel = discord_client.channels_to_write[MY_GUILD_ID]

    assert len(channel.messages_sent) == 3

    # Verify the contents of the first message (winner message)
    expected_message_1 = (
        f"@Slugger is the winner of the *LoL Jeopardy {JEOPADY_EDITION}* with **800 points**!!! "
        "All hail the king :crown:\n"
        "They get a special badge of honor on Discord and wins a **1350 RP** skin!"
    )
    assert channel.messages_sent[0] == expected_message_1

    # Verify the contents of the second message (most hits message)
    expected_message_2 = (
        "Honorable mention to @Murt for answering the most questions correct "
        "with **3** correct answers! Big nerd legend over here :nerd:!"
    )
    assert channel.messages_sent[1] == expected_message_2

    # Verify the contents of the third message (most buzzer hits)
    expected_message_3 = (
        "Shout out to @Eddie Smurphy for buzzing in the most with "
        "**6** buzz-ins! Big respect for not being a poon!"
    )
    assert channel.messages_sent[2] == expected_message_3

@pytest.mark.asyncio
async def test_discord_message_ties(discord_client):
    player_data = [
        {"disc_id": 2, "name": "Dave", "avatar": None, "score": 800, "buzzes": 4, "hits": 3, "misses": 1, "color": "F30B0B"},
        {"disc_id": 3, "name": "Murt", "avatar": None, "score": 800, "buzzes": 7, "hits": 4, "misses": 3, "color": "CCCC00"},
        {"disc_id": 4, "name": "Muds", "avatar": None, "score": 500, "buzzes": 7, "hits": 5, "misses": 2, "color": "FF00FF"},
        {"disc_id": 5, "name": "Nø", "avatar": None, "score": 200, "buzzes": 6, "hits": 5, "misses": 1, "color": "00FFFF"},
    ]

    await discord_client.announce_jeopardy_winner(player_data, MY_GUILD_ID)

    channel = discord_client.channels_to_write[MY_GUILD_ID]

    assert len(channel.messages_sent) == 3

    # Verify the contents of the first message (winner message)
    expected_message_1 = (
        f"@Slugger and @Murt both won the *LoL Jeopardy {JEOPADY_EDITION}* with "
        "**800 points**!!!\nThey both get a special badge of honor "
        "on Discord and each win a **975 RP** skin!"
    )
    assert channel.messages_sent[0] == expected_message_1

    # Verify the contents of the second message (most hits message)
    expected_message_2 = (
        "Honorable mentions to @Eddie Smurphy and @Nønø for having the most correct answers, "
        "both answering correct **5** times! They are both nerds :nerd:!"
    )
    assert channel.messages_sent[1] == expected_message_2

    # Verify the contents of the third message (most buzzer hits)
    expected_message_3 = (
        "Shout out to @Murt and @Eddie Smurphy for having the most buzz-ins, both buzzing in "
        "**7** times! They are both real G's!"
    )
    assert channel.messages_sent[2] == expected_message_3

@pytest.mark.skip()
#@pytest.mark.asyncio
async def test_all_questions():
    turn_id = 0
    player_data = [
        (CONTESTANT_IDS[0], 0, "Dave", "F30B0B"),
        (CONTESTANT_IDS[1], 0, "Murt", "CCCC00"),
        (CONTESTANT_IDS[2], 0, "Muds", "FF00FF"),
        (CONTESTANT_IDS[3], 0, "Nø", "00FFFF")
    ]
    async with ContextHandler() as context:
        #context.presenter_page.on("requestfinished", lambda req: print("Request:", req.url))

        await context.open_presenter_selection_page(1, 0, turn_id, player_data)

        for round_num in range(2):
            question_num = 0
            for category in ("mechanics", "lore", "icons", "outlines", "wrong", "audio"):
                for difficulty in range(1, 6):
                    # Go to question page
                    await context.open_presenter_question_page(round_num + 1, category, difficulty, question_num, turn_id, player_data)
                    await asyncio.sleep(1)

                    await context.show_question()
                    await asyncio.sleep(1)

                    await context.screenshot_views((round_num * 30) + question_num + 1)

                    question_num += 1

def test_questions_well_formed(config):
    def get_base_path(filename):
        return f"{config.static_folder}/img/jeopardy/{filename}"

    def get_question_path(filename):
        return f"{config.static_folder}/img/jeopardy/{JEOPARDY_ITERATION}/{filename}"

    with open(f"{config.static_folder}/data/jeopardy_questions_{JEOPARDY_ITERATION}.json", "r", encoding="utf-8") as fp:
        all_question_data = json.load(fp)

    mandatory_category_keys = set(["name", "order", "background", "tiers"])
    optional_category_keys = set(["buzz_time"])
    mandatory_tiers_keys = set(["value", "questions"])
    mandatory_question_keys = set(["question", "answer"])
    optional_question_keys = set(
        [
            "choices",
            "image",
            "explanation",
            "answer_image",
            "video",
            "tips",
            "height",
            "border",
            "volume"
        ]
    )

    for index, category in enumerate(all_question_data):
        category_data = all_question_data[category]

        for key in mandatory_category_keys:
            assert key in category_data, "Mandatory category key missing"

        assert len(set(category_data.keys()) - (mandatory_category_keys.union(optional_category_keys))) == 0, "Wrong category keys"

        assert os.path.exists(get_base_path(category_data["background"])), "Background missing"

        tiers = all_question_data[category]["tiers"] if index < 6 else [all_question_data[category]["tiers"][-1]]

        for tier_data in tiers:
            assert set(tier_data.keys()) == mandatory_tiers_keys, "Wrong tier keys"

            expected_num_questions = JEOPARDY_REGULAR_ROUNDS if index < 6 else 1
            assert len(tier_data["questions"]) == expected_num_questions

            for question_data in tier_data["questions"]:
                for key in mandatory_question_keys:
                    assert key in question_data, "Mandatory question key missing"

                assert len(set(question_data.keys()) - (mandatory_question_keys.union(optional_question_keys))) == 0, "Wrong question keys"

                for key in ("image", "answer_image", "video"):
                    if key in question_data:
                        assert os.path.exists(get_question_path(question_data[key])), "Question image/video missing"
                        assert "height" in question_data

                if "choices" in question_data:
                    choices = question_data["choices"]
                    assert isinstance(choices, list) and len(choices) == 4, "Wrong amount of choices for multiple choice"
                    assert question_data["answer"] in choices, "Answer is not in the list of choices"

    with open(f"{config.static_folder}/data/jeopardy_used_{JEOPARDY_ITERATION}.json", "r", encoding="utf-8") as fp:
        used_data = json.load(fp)

    question_keys = set(all_question_data.keys())
    used_keys = set(used_data.keys())

    assert question_keys == used_keys, "Used questions don't match"
