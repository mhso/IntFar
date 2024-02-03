import asyncio
from concurrent.futures import TimeoutError as FutureTimeout, CancelledError
from time import time, sleep
from multiprocessing import Pipe
from multiprocessing.connection import wait

from mhooge_flask.logging import logger

def listen_for_request(disc_client, event_loop):
    max_timeout = 60
    max_connections = 100
    timeouts = {}
    connections = {0: disc_client.flask_conn}

    while not disc_client.is_closed():
        conns_to_remove = []

        for conn in wait(connections.values(), 0.001): # Loop through pending connections.
            try:
                conn_id, command_types, commands, paramses = conn.recv()
                results = []

                for (command_type, command, params) in zip(command_types, commands, paramses):
                    result = None

                    if command_type == "register": # Register new connection.
                        our_conn, new_conn = Pipe()
                        connections[conn_id] = our_conn

                        if len(connections) > max_connections:
                            # If number of connection exceed 'max_connections', we halve
                            # the time it takes for connections to time out to free up space.
                            max_timeout = max_timeout // 2
    
                        timeouts[conn_id] = time()
                        logger.debug(f"Session ID {conn_id} connection.")
                        result = new_conn

                    elif command_type == "func": # Return data from Discord client to a user.
                        if params[0] is None and len(params) == 1:
                            result = disc_client.__getattribute__(command)()
                        else:
                            result = disc_client.__getattribute__(command)(*params)

                        if asyncio.iscoroutine(result):
                            try:
                                future = asyncio.run_coroutine_threadsafe(result, event_loop)
                                result = future.result(3)
                            except (FutureTimeout, CancelledError):
                                # Log error
                                logger.bind(
                                    command_type=command_type,
                                    command=command,
                                    params=params
                                ).exception(f"Exception during Discord request")

                                result = None

                    elif command_type == "bot_command":
                        pass # Do bot command.

                    results.append(result)

                conn.send(results)

            except (EOFError, BrokenPipeError, ConnectionResetError):
                # Connection to user has stopped.
                logger.error(f"App Listener Exception")

                # Add crashed connection to those that should be removed.
                for conn_id in connections:
                    if connections[conn_id] == conn:
                        conns_to_remove.append(conn_id)

        now = time()
        for conn_id in timeouts: # Check to see if any connection has timed out.
            if now - timeouts[conn_id] > max_timeout:
                conns_to_remove.append(conn_id)

        for conn_id in conns_to_remove: # Remove/forget timed out connections.
            logger.debug(f"Session ID {conn_id} timed out.")

            if conn_id in timeouts:
                del timeouts[conn_id]

            connections[conn_id].close()
            del connections[conn_id]

        sleep(0.01)
