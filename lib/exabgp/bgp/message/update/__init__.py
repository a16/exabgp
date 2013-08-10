# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.address import Address

from exabgp.bgp.message import Message,prefix
from exabgp.bgp.message.update.attribute.id import AttributeID as AID
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI

from exabgp.bgp.message.notification import Notify

# =================================================================== Update

class Update (Message):
	TYPE = chr(0x02)

	def new (self,nlris,attributes):
		self.nlris = nlris
		self.attributes = attributes
		return self

	# The routes MUST have the same attributes ...
	def announce (self,negotiated):
		asn4 = negotiated.asn4
		local_as = negotiated.local_as
		peer_as = negotiated.peer_as

		attr = self.attributes.pack(asn4,local_as,peer_as)
		msg_size = negotiated.msg_size - 2 - 2 - len(attr)  # 2 bytes for each of the two prefix() header

		all_nlri = []
		sorted_mp = {}

		for nlri in self.nlris:
			if nlri.family() in negotiated.families:
				if nlri.afi == AFI.ipv4 and nlri.safi in [SAFI.unicast, SAFI.multicast] and nlri.nexthop == self.attributes.get(AID.NEXT_HOP,None):
					all_nlri.append(nlri)
				else:
					sorted_mp.setdefault((nlri.afi,nlri.safi),[]).append(nlri)

		if not all_nlri and not sorted_mp:
			return

		packed_mp = ''
		packed_nlri = ''

		families = sorted_mp.keys()
		while families:
			family = families.pop()
			mps = sorted_mp[family]
			addpath = negotiated.addpath.send(*family)
			mp_packed_generator = MPRNLRI(mps).packed_attributes(addpath)
			try:
				while True:
					packed = mp_packed_generator.next()
					if len(packed_mp + packed) > msg_size:
						if not packed_mp:
							raise Notify(6,0,'attributes size is so large we can not even pack on MPURNLRI')
						yield self._message(prefix('') + prefix(attr + packed_mp))
						packed_mp = packed
					else:
						packed_mp += packed
			except StopIteration:
				pass

		addpath = negotiated.addpath.send(AFI.ipv4,SAFI.unicast)
		while all_nlri:
			nlri = all_nlri.pop()
			packed = nlri.pack(addpath)
			if len(packed_mp + packed_nlri + packed) > msg_size:
				if not packed_nlri and not packed_mp:
					raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
				yield self._message(prefix('') + prefix(attr + packed_mp) + packed_nlri)
				packed_mp = ''
				packed_nlri = packed
			else:
				packed_nlri += packed

		if packed_mp or packed_nlri:
			yield self._message(prefix('') + prefix(attr + packed_mp) + packed_nlri)

	# print ''.join(['%02X' % ord(_) for _ in self._message(prefix('') + prefix(attr + packed_mp) + packed_nlri)])

	def withdraw (self,negotiated=None):
		msg_size = negotiated.msg_size - 4  # 2 bytes for each of the two prefix() header

		#packed_nlri = {}
		#packed_mp = {}

		all_nlri = []
		sorted_mp = {}

		for nlri in self.nlris:
			if nlri.family() in negotiated.families:
				if nlri.afi == AFI.ipv4 and nlri.safi in [SAFI.unicast, SAFI.multicast]:
					all_nlri.append(nlri)
				else:
					sorted_mp.setdefault((nlri.afi,nlri.safi),[]).append(nlri)

		if not all_nlri and not sorted_mp:
			return

		packed_mp = ''
		packed_nlri = ''

		addpath = negotiated.addpath.send(AFI.ipv4,SAFI.unicast)

		while all_nlri:
			nlri = all_nlri.pop()
			packed = nlri.pack(addpath)
			if len(packed_nlri + packed) > msg_size:
				if not packed_nlri:
					raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
				yield self._message(prefix(packed_nlri))
				packed_nlri = packed
			else:
				packed_nlri += packed


		families = sorted_mp.keys()
		while families:
			family = families.pop()
			mps = sorted_mp[family]
			addpath = negotiated.addpath.send(*family)
			mp_packed_generator = MPURNLRI(mps).packed_attributes(addpath)
			try:
				while True:
					packed = mp_packed_generator.next()
					if len(packed_nlri + packed_mp + packed) > msg_size:
						if not packed_mp and not packed_nlri:
							raise Notify(6,0,'attributes size is so large we can not even pack one MPURNLRI')
						if packed_mp:
							yield self._message(prefix(packed_nlri) + prefix(packed_mp))
						else:
							yield self._message(prefix(packed_nlri) + prefix(''))
						packed_nlri = ''
						packed_mp = packed
					else:
						packed_mp += packed
			except StopIteration:
				pass

		if packed_mp:
			yield self._message(prefix(packed_nlri) + prefix(packed_mp))
		else:
			yield self._message(prefix(packed_nlri) + prefix(''))

	# print ''.join(['%02X' % ord(_) for _ in self._message(prefix(packed_nlri) + prefix(''))])

	def index (self,number):
		raise RuntimeError('is it really needed ?')
		return self.nlris[number].index()

	def __str__ (self):
		return '\n'.join([self.extensive(_) for _ in range(len(self.nlris))])
