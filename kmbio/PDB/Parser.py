from abc import ABC, abstractmethod


class Parser(ABC):

    @abstractmethod
    def get_structure(self, filename, structure_id=None, bioassembly=0):
        """Return the structure.

        Parameters
        ----------
        filename : :class:`str`
            Name of the file containing the structure.
        structure_id : :class:`str` | :class:`None`
            ID to assign to the newly generated structure.
            If `None`, try to read the ID from the structure file.
        bioassembly : :class:`int`
            The ID of the bioassembly to return.
            If ``0``, return the raw structure (no bioassembly transformation).
        """
        raise NotImplementedError
