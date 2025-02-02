# SPDX-License-Identifier: GPL-2.0+
# Copyright (c) 2018 Google, Inc
# Written by Simon Glass <sjg@chromium.org>
#

# Support for a Chromium OS verified boot block, used to sign a read-write
# section of the image.

from collections import OrderedDict
import os

from binman.entry import EntryArg
from binman.etype.collection import Entry_collection

from dtoc import fdt_util
from patman import tools

class Entry_vblock(Entry_collection):
    """An entry which contains a Chromium OS verified boot block

    Properties / Entry arguments:
        - content: List of phandles to entries to sign
        - keydir: Directory containing the public keys to use
        - keyblock: Name of the key file to use (inside keydir)
        - signprivate: Name of provide key file to use (inside keydir)
        - version: Version number of the vblock (typically 1)
        - kernelkey: Name of the kernel key to use (inside keydir)
        - preamble-flags: Value of the vboot preamble flags (typically 0)

    Output files:
        - input.<unique_name> - input file passed to futility
        - vblock.<unique_name> - output file generated by futility (which is
            used as the entry contents)

    Chromium OS signs the read-write firmware and kernel, writing the signature
    in this block. This allows U-Boot to verify that the next firmware stage
    and kernel are genuine.
    """
    def __init__(self, section, etype, node):
        super().__init__(section, etype, node)
        self.futility = None
        (self.keydir, self.keyblock, self.signprivate, self.version,
         self.kernelkey, self.preamble_flags) = self.GetEntryArgsOrProps([
            EntryArg('keydir', str),
            EntryArg('keyblock', str),
            EntryArg('signprivate', str),
            EntryArg('version', int),
            EntryArg('kernelkey', str),
            EntryArg('preamble-flags', int)])

    def GetVblock(self, required):
        """Get the contents of this entry

        Args:
            required: True if the data must be present, False if it is OK to
                return None

        Returns:
            bytes content of the entry, which is the signed vblock for the
                provided data
        """
        # Join up the data files to be signed
        input_data = self.GetContents(required)
        if input_data is None:
            return None

        uniq = self.GetUniqueName()
        output_fname = tools.get_output_filename('vblock.%s' % uniq)
        input_fname = tools.get_output_filename('input.%s' % uniq)
        tools.write_file(input_fname, input_data)
        prefix = self.keydir + '/'
        stdout = self.futility.sign_firmware(
            vblock=output_fname,
            keyblock=prefix + self.keyblock,
            signprivate=prefix + self.signprivate,
            version=f'{self.version,}',
            firmware=input_fname,
            kernelkey=prefix + self.kernelkey,
            flags=f'{self.preamble_flags}')
        if stdout is not None:
            data = tools.read_file(output_fname)
        else:
            # Bintool is missing; just use 4KB of zero data
            self.record_missing_bintool(self.futility)
            data = tools.get_bytes(0, 4096)
        return data

    def ObtainContents(self):
        data = self.GetVblock(False)
        if data is None:
            return False
        self.SetContents(data)
        return True

    def ProcessContents(self):
        # The blob may have changed due to WriteSymbols()
        data = self.GetVblock(True)
        return self.ProcessContentsUpdate(data)

    def AddBintools(self, btools):
        self.futility = self.AddBintool(btools, 'futility')
