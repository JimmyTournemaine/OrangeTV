"""
<plugin key="OrangeTV" name="Orange TV Players" author="tzimy" version="0.0.1">
    <description>
      Plugin to control an Orange TV decoder
    </description>
    <params>
        <param field="Address" label="IP Address" width="200px" required="true"/>
        <param field="Port" label="Port" width="40px" required="true" default="8080"/>
        <param field="Interval" label="Interval" width="40px" required="true" default="30"/>
    </params>
</plugin>
"""

import json
errmsg = ""
try:
    import Domoticz
except Exception as e:
    errmsg += "Domoticz core start error: "+str(e)


class ContextFactory:

    def create(self, conn, status):
        osdContext = status['osdContext']

        if osdContext == 'MAIN_PROCESS':
            context = OffContext()
        elif osdContext == 'LIVE':
            context = LiveContext(status['playedMediaId'])
        else:
            context = OnContext(osdContext)

        return context.connect(conn)


class Context:
    def __init__(self, state, text):
        self.state = state
        self.text = text

    def connect(self, tvConn):
        self.conn = tvConn
        return self

    def send(self, key, mode=0, op="01"):
        self.conn.Send(
            {'Verb': 'GET', 'URL': f'/remoteControl/cmd?operation={op}&mode={mode}&key={key}'})


class OffContext(Context):
    def __init__(self):
        super().__init__(State.OFF, 'Off')


class OnContext(Context):
    def __init__(self, status):
        super().__init__(State.ON, status.title())

    def onHome(self):
        self.send(139)

    def onInfo(self):
        pass

    def onBack(self):
        self.send(158)

    def onContextMenu(self):
        self.send(139)

    def onSelect(self):
        self.send(352)

    def onUp(self):
        self.send(103)

    def onLeft(self):
        self.send(105)

    def onRight(self):
        self.send(106)

    def onDown(self):
        self.send(108)

    def onChannels(self):
        pass

    def onChannelUp(self):
        self.send(402)

    def onChannelDown(self):
        self.send(403)

    def onFullScreen(self):
        pass

    def onShowSubtitles(self):
        self.send(0)

    def onStop(self):
        pass

    def onVolumeUp(self):
        self.send(115)

    def onVolumeDown(self):
        self.send(114)

    def onMute(self):
        self.send(113)

    def onPlayPause(self):
        self.send(164)

    def onFastForward(self):
        self.send(159)

    def onBigStepForward(self):
        pass

    def onRewind(self):
        self.send(168)

    def onBigStepBack(self):
        pass


class LiveContext(OnContext):
    def __init__(self, playId):
        super().__init__(State.PLAYING, f'Live: {epg_map[playId]}')


class State:
    OFF = 0
    ON = 1
    PLAYING = 7
    DISCONNECTED = 8
    UNKNOWN = 10


def is_running(Device):
    return Device.nValue > 0


def load_epg():
    with open("/home/domoticz/domoticz/plugins/OrangeTV/epg_id.json") as epg_file:
        epg = json.load(epg_file)
    return {v: k for k, v in epg.items()}


epg_map = load_epg()


class Plugin:
    status = {}

    def __init__(self):
        return

    def onStart(self):
        if errmsg == "":
            # Debugging
            Domoticz.Debugging(1)

            if (len(Devices) == 0):
                Domoticz.Device(Name="Status",  Unit=1, Type=244,
                                Subtype=73, Switchtype=17, Used=1).Create()
                Domoticz.Log("Device created.")

            self.OrangeTVConn = Domoticz.Connection(
                Name="OrangeTVConn", Transport="TCP/IP", Protocol="HTTP", Address=Parameters["Address"], Port=Parameters["Port"])
            self.OrangeTVConn.Connect()

            Domoticz.Heartbeat(Parameters["Interval"])
        else:
            Domoticz.Error(
                "Plugin::onStart: Domoticz Python env error {}".format(errmsg))

    def onConnect(self, Connection, Status, Description):
        if (Status == 0):
            Domoticz.Log("Connected successfully to: " +
                         Connection.Address+":"+Connection.Port)
        else:
            Domoticz.Log("Failed to connect ("+str(Status)+") to: " +
                         Connection.Address+":"+Connection.Port)
            Domoticz.Debug("Failed to connect ("+str(Status)+") to: " +
                           Connection.Address+":"+Connection.Port+" with error: "+Description)
        return True

    def onDisconnect(self, Connection):
        Devices[1].Update(8, 'Disconnected')

    def onMessage(self, Connection, Data):
        if int(Data['Status']) == 200:
            Response = json.loads(Data['Data'])

            # Update player status
            if 'result' in Response and 'data' in Response['result'] and 'osdContext' in Response['result']['data']:
                self.onStatusUpdated(Response['result']['data'])
                return

            Domoticz.Log(f"Unexpected response: {str(Data)}")
        else:
            Domoticz.Log(f"Error response: {str(Data)}")

    def onCommand(self, Unit, Command, Level, Color):
        Domoticz.Debug("onCommand called for Unit " + str(Unit) +
                       ": Parameter '" + str(Command) + "', Level: " + str(Level))
        if Unit in Devices:
            Device = Devices[Unit]
            # Switch Off
            if Command == 'Off' and is_running(Device):
                self.OrangeTVConn.Send(
                    {'Verb': 'GET', 'URL': '/remoteControl/cmd?operation=01&mode=0&key=116'})
                Device.Update(0, 'Off')
            # Switch On
            elif Command == 'On' and not is_running(Device):
                self.OrangeTVConn.Send(
                    {'Verb': 'GET', 'URL': '/remoteControl/cmd?operation=01&mode=0&key=116'})
                Device.Update(1, 'On')
            # Other command on a running device
            elif f"on{Command}" in self.context and is_running(Device):
                getattr(self.context, f"on{Command}")()
            # Unknown command
            else:
                Domoticz.Error(f"Unknown command {str(Command)}")

    def onHeartbeat(self):
        if 1 in Devices and self.OrangeTVConn.Connected():
            self.OrangeTVConn.Send(
                {'Verb': 'GET', 'URL': '/remoteControl/cmd?operation=10'})

    def onStatusUpdated(self, status):
        Domoticz.Debug(f"onStatusUpdated: status={str(status)}")
        if 1 in Devices:
            self.context = ContextFactory().create(self.OrangeTVConn, status)
            Devices[1].Update(self.context.state, self.context.text)

# Domoticz Python Plugin Interface


global _plugin
_plugin = Plugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)


def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)


def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)


def onCommand(Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Color)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()
