import importlib
import socket


PROTOBUFS = {}
def import_pb(pb: int, addname: str = ""):
	module = importlib.import_module(f".p{pb}{addname}_pb_pb2", "azlassets.proto")
	PROTOBUFS[pb] = module

def import_pb_with_retry(pb: int):
	try:
		import_pb(pb)
	except ModuleNotFoundError:
		import_pb(pb, "min")

class InvalidHeaderError(Exception): pass

class BasicCommand:
	def __init__(self, command_id: int, index: int=0):
		pbpackage = command_id//1000
		if pbpackage not in PROTOBUFS:
			try:
				import_pb_with_retry(pbpackage)
			except ModuleNotFoundError:
				print(f'Command Package {pbpackage} does not exist (From cmd={command_id}).')

		pbpak = PROTOBUFS[pbpackage]
		if hasattr(pbpak, 'cs_'+str(command_id)):
			self.command_id = command_id
			self.index = index
			self.pb = getattr(pbpak, 'cs_'+str(command_id))()
		elif hasattr(pbpak, 'sc_'+str(command_id)):
			self.command_id = command_id
			self.index = index
			self.pb = getattr(pbpak, 'sc_'+str(command_id))()
		else:
			print(f'Command {command_id} is not registered.')


ADV_HEADER_LEN = 7
HEADER_LEN = 2
HEADER_NOID_LEN = ADV_HEADER_LEN - HEADER_LEN

def serialize_pb(basic_pb_command):
	payload = bytearray(basic_pb_command.pb.SerializeToString())

	header_bytes = ((len(payload) or 1) + HEADER_NOID_LEN).to_bytes(2, byteorder='big')
	command_id_bytes = basic_pb_command.command_id.to_bytes(2, byteorder='big')
	index_bytes = basic_pb_command.index.to_bytes(2, byteorder='big')

	command_bytes = bytearray(ADV_HEADER_LEN)
	command_bytes[0] = header_bytes[0]
	command_bytes[1] = header_bytes[1]
	command_bytes[3] = command_id_bytes[0]
	command_bytes[4] = command_id_bytes[1]
	command_bytes[5] = index_bytes[0]
	command_bytes[6] = index_bytes[1]
	command_bytes.extend(payload)
	return command_bytes


def deserialize_header(header_bytes):
	if not header_bytes[2] == 0:
		raise InvalidHeaderError('Received invalid header.')
	payload_size = (header_bytes[0] << 8 | header_bytes[1]) - HEADER_NOID_LEN
	command_id = header_bytes[3] << 8 | header_bytes[4]
	index = header_bytes[5] << 8 | header_bytes[6]
	return payload_size, command_id, index

def deserialize_pb(command_id, index, payload_bytes):
	basiccmd = BasicCommand(command_id)
	if hasattr(basiccmd, 'pb'):
		basiccmd.pb.ParseFromString(payload_bytes)
		print(f'Successfully received cmd={command_id} with idx={index}.')
		return basiccmd


# PROTOBUF HELPER METHODS
class ConnectionSocket(socket.socket):
	def __init__(self, blocking=True):
		super().__init__(socket.AF_INET, socket.SOCK_STREAM)
		self.setblocking(blocking)

	def disconnect(self):
		self.close()

	def send_command(self, commandid, index, **kwargs):
		print(f"Sending Command {commandid}.")
		command = BasicCommand(commandid, index)
		for k, v in kwargs.items():
			setattr(command.pb, k, v)
		self.send(serialize_pb(command))

	def recv_command(self):
		header = self.recv_bytes(ADV_HEADER_LEN)
		payload_size, command_id, index = deserialize_header(header)
		payload = self.recv_bytes(payload_size)
		return deserialize_pb(command_id, index, payload)

	def recv_bytes(self, bytesize:int):
		data = b''
		while len(data) < bytesize:
			data += self.recv(bytesize - len(data))
		return data

def get_version_response(gateip, gateport):
	with ConnectionSocket() as socket:
		socket.connect((gateip, gateport))
		socket.send_command(
			10800,
			0,
			state=21,
			platform='0'
		)
		result = socket.recv_command()
	return result
