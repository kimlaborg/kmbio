# Copyright (C) 2002, Thomas Hamelryck (thamelry@binf.ku.dk)
# This code is part of the Biopython distribution and governed by its
# license.  Please see the LICENSE file that should have been included
# as part of this package.
"""Output of PDB files."""
import logging
from pathlib import Path
from typing import TextIO, Union

from Bio.Data.IUPACData import atom_weights

from kmbio.PDB import Structure, StructureBuilder

logger = logging.getLogger(__name__)


def save(
    structure: Structure, filename: Union[str, Path], include_disordered=True,
):
    """Save kmbio `Structure` object as a PDB.

    Examples:
        >>> tmpfile = tempfile.NamedTemporaryFile()
        >>> s1 = fetch_structure('4dkl')
        >>> save_structure(s1, tmpfile.name)
        >>> s2 = load_structure(tmpfile.name)
        >>> allequal(s1, s2)
        True
    """
    io = PDBIO()
    io.set_structure(structure)
    select = Select() if include_disordered else NotDisordered()
    io.save(filename, select=select)


class Select(object):
    """Select everything fo PDB output (for use as a bas class).

    Default selection (everything) during writing - can be used as base class
    to implement selective output. This selects which entities will be written out.
    """

    def __repr__(self):
        return "<Select all>"

    def accept_model(self, model):
        """Overload this to reject models for output."""
        return 1

    def accept_chain(self, chain):
        """Overload this to reject chains for output."""
        return 1

    def accept_residue(self, residue):
        """Overload this to reject residues for output."""
        return 1

    def accept_atom(self, atom):
        """Overload this to reject atoms for output."""
        return 1


class NotDisordered(Select):
    """Select only non-disordered residues and set their altloc flag to ' '.

    Source: http://biopython.org/wiki/Remove_PDB_disordered_atoms
    """

    def accept_residue(self, residue):
        if not residue.disordered:
            return True
        elif any(self.accept_atom(atom) for atom in residue):
            residue.disordered = False
            return True
        else:
            logger.debug("Ignoring residue %s.", residue)
            return False

    def accept_atom(self, atom):
        if not atom.disordered_flag:
            return True
        elif atom.altloc == "A":
            atom.disordered_flag = False
            atom.altloc = " "
            return True
        else:
            logger.debug("Ignoring atom %s.", atom)
            return False


class PDBIO(object):
    """Write a Structure object (or a subset of a Structure object) as a PDB file.

    Example:

        >>> p=PDBParser()
        >>> s=p.get_structure("1fat", "1fat.pdb")
        >>> io=PDBIO()
        >>> io.set_structure(s)
        >>> io.save("out.pdb")
    """

    def __init__(self, use_model_flag=0):
        """Creat the PDBIO object.

        @param use_model_flag: if 1, force use of the MODEL record in output.
        @type use_model_flag: int
        """
        self.use_model_flag = use_model_flag

    # private mathods

    def _get_atom_line(
        self, atom, hetfield, segid, atom_number, resname, resseq, icode, chain_id, charge="  "
    ):
        """Returns an ATOM PDB string (PRIVATE)."""
        if hetfield != " ":
            record_type = "HETATM"
        else:
            record_type = "ATOM  "
        if atom.element:
            element = atom.element.strip().upper()
            if element.capitalize() not in atom_weights:
                raise ValueError("Unrecognised element %r" % atom.element)
            element = element.rjust(2)
        else:
            element = "  "
        name = atom.fullname
        altloc = atom.altloc
        x, y, z = atom.coord
        bfactor = atom.bfactor
        occupancy = atom.occupancy
        try:
            occupancy_str = "%6.2f" % occupancy
        except TypeError:
            if occupancy is None:
                occupancy_str = " " * 6
                logger.warning("Missing occupancy in atom %s written as blank", repr(atom.full_id))
            else:
                raise TypeError("Invalid occupancy %r in atom %r" % (occupancy, atom.full_id))

        bfactor_str = f"{bfactor:6.2f}"
        if len(bfactor_str) > 6:
            bfactor_str = bfactor_str[: bfactor_str.index(".")]

        line = (
            f"{record_type:6s}"
            f"{atom_number:>5d} "
            f"{name.strip().ljust(3).rjust(4):4s}"
            f"{altloc:1s}"
            f"{resname:>3s}"
            f"{chain_id:>2s}"
            f"{resseq:4d}"
            f"{icode:1s}   "
            f"{x:8.3f}"
            f"{y:8.3f}"
            f"{z:8.3f}"
            f"{occupancy_str:6s}"
            f"{bfactor_str:6s}"
            f"{segid:>7s}"
            f"{element:>5s}"
            f"{charge:>2s}"
            "\n"
        )
        assert len(line) == 81, (len(line), line)
        return line

    # Public methods

    def set_structure(self, pdb_object):
        # Check what the user is providing and build a structure appropriately
        if pdb_object.level == "S":
            structure = pdb_object
        else:
            sb = StructureBuilder()
            sb.init_structure("pdb")
            sb.init_seg(" ")
            # Build parts as necessary
            if pdb_object.level == "M":
                sb.structure.add(pdb_object)
                self.structure = sb.structure
            else:
                sb.init_model(0)
                if pdb_object.level == "C":
                    sb.structure[0].add(pdb_object)
                else:
                    sb.init_chain("A")
                    if pdb_object.level == "R":
                        try:
                            parent_id = pdb_object.parent.id
                            sb.structure[0]["A"].id = parent_id
                        except Exception:
                            pass
                        sb.structure[0]["A"].add(pdb_object)
                    else:
                        # Atom
                        sb.init_residue("DUM", " ", 1, " ")
                        try:
                            parent_id = pdb_object.parent.parent.id
                            sb.structure[0]["A"].id = parent_id
                        except Exception:
                            pass
                        sb.structure[0]["A"].ix[0].add(pdb_object)

            # Return structure
            structure = sb.structure
        self.structure = structure

    def save(
        self,
        file: Union[str, Path, TextIO],
        select=Select(),
        write_end: bool = True,
        atom_numbering: str = "by_chain",
    ) -> None:
        """
        Args:
            file: output file
            select: selects which entities will be written.
                Typically select is a subclass of L{Select}.
                It should have the following methods:

                - accept_model(model)
                - accept_chain(chain)
                - accept_residue(residue)
                - accept_atom(atom)

                These methods should return 1 if the entity is to be
                written out, 0 otherwise.
            write_end:
            atom_numbering: One of {"keep", "model", "chain"}

                - keep - Keeps atom numbering from the input model.
                - by_model - Numbers atoms ``1..N``, where ``N`` is the length of the model.
                - by_chain - Numbers atoms ``1..N``, where ``N`` is the length of the chain.
        """
        assert atom_numbering in ["keep", "by_model", "by_chain"]

        get_atom_line = self._get_atom_line
        if isinstance(file, (str, Path)):
            fp = open(file, "w")
            close_file = 1
        else:
            # filehandle, I hope :-)
            fp = file
            close_file = 0
        # multiple models?
        if len(self.structure) > 1 or self.use_model_flag:
            model_flag = 1
        else:
            model_flag = 0
        for model in self.structure:
            if not select.accept_model(model):
                continue
            if atom_numbering == "by_model":
                atom_number = 1
            # necessary for ENDMDL
            # do not write ENDMDL if no residues were written
            # for this model
            model_residues_written = 0
            if model_flag:
                fp.write("MODEL      %s\n" % model.serial_num)
            for chain in model:
                if not select.accept_chain(chain):
                    continue
                chain_id = chain.id
                if atom_numbering == "by_chain":
                    atom_number = 1
                # necessary for TER
                # do not write TER if no residues were written
                # for this chain
                chain_residues_written = 0
                for residue in chain.get_unpacked_list():
                    if not select.accept_residue(residue):
                        continue
                    hetfield, resseq, icode = residue.id
                    resname = residue.resname
                    segid = residue.segid
                    for atom in residue.get_unpacked_list():
                        if select.accept_atom(atom):
                            chain_residues_written = 1
                            model_residues_written = 1
                            if atom_numbering == "keep":
                                atom_number = atom.serial_number
                            s = get_atom_line(
                                atom, hetfield, segid, atom_number, resname, resseq, icode, chain_id
                            )
                            fp.write(s)
                            atom_number += 1
                if chain_residues_written:
                    fp.write("TER\n")
            if model_flag and model_residues_written:
                fp.write("ENDMDL\n")
        if write_end:
            fp.write("END\n")
        if close_file:
            fp.close()


if __name__ == "__main__":

    from kmbio.PDB.PDBParser import PDBParser

    import sys

    p = PDBParser(PERMISSIVE=True)

    s = p.get_structure("test", sys.argv[1])

    io = PDBIO()
    io.set_structure(s)
    io.save("out1.pdb")

    with open("out2.pdb", "w") as fp:
        s1 = p.get_structure("test1", sys.argv[1])
        s2 = p.get_structure("test2", sys.argv[2])
        io = PDBIO(1)
        io.set_structure(s1)
        io.save(fp)
        io.set_structure(s2)
        io.save(fp, write_end=True)
