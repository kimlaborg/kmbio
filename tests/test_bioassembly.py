import json
import logging
import os.path as op
import random
import re

import pytest
import yaml

import kmbio.PDB
from conftest import parametrize
from kmbio.PDB import (DEFAULT_ROUTES, MMCIFParser, PDBParser, ProcessRemark350, allequal,
                       get_mmcif_bioassembly_data, mmcif2dict, open_url, sort_structure)

random.seed(42)
logger = logging.getLogger(__name__)

URL = "ftp://ftp.wwpdb.org/pub/pdb/data/"
NUMBER_OF_SAMPLES = 20

# PDB_BIOASSEMBLY_DATA

with open(op.join(op.splitext(__file__)[0], 'test_bioassembly.json'), 'rt') as ifh:
    # (remark_350_data, bioassembly_data_ref)
    PDB_BIOASSEMBLY_DATA = json.load(ifh)


@pytest.mark.parametrize(
    "remark_350_data, bioassembly_data_ref",
    [
        # (PDB 'REMARK 350' data, expected bioassembly data)
        (d['remark_350_data'], d['bioassembly_data']) for d in PDB_BIOASSEMBLY_DATA
    ])
def test_process_line_350_1(remark_350_data, bioassembly_data_ref):
    """Make sure that ProcessRemark350 correctly parses bioassembly data in PDBs.

    Uses a reference dictionary for test cases.
    """
    parser = ProcessRemark350()
    bioassembly_data = parser.process_lines(remark_350_data)
    bioassembly_data = json.loads(json.dumps(bioassembly_data))
    assert bioassembly_data == bioassembly_data_ref


# #############################################################################
# TEST_DATA
# #############################################################################

TEST_DATA = [
    # (pdb_id, bioassembly_id)
    ('1y0x', 2),
    ('1y0o', 1),
    ('1y0y', 1),
    ('1dvf', 1),
]


@pytest.mark.parametrize("pdb_id, bioassembly_id", TEST_DATA)
def test_process_line_350_2(pdb_id, bioassembly_id):
    """Make sure that ProcessRemark350 correctly parses bioassembly data in PDBs.

    Only validates for the presence of the bioassembly id in bioassembly_data.
    """
    pdb_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'pdb')
    with open_url(pdb_url) as ifh:
        data = [l for l in ifh if l.startswith('REMARK 350')]
    pr350 = ProcessRemark350()
    bioassembly_data = pr350.process_lines(data)
    assert str(bioassembly_id) in bioassembly_data
    logger.debug(bioassembly_data)


# #############################################################################
# TEST_DATA
# #############################################################################

with open(op.join(op.splitext(__file__)[0], 'test_data.yml'), 'rt') as ifh:
    TEST_DATA = yaml.load(ifh)


@parametrize("pdb_id", TEST_DATA['pdb_vs_mmcif_bioassembly_data'])
def test_pdb_vs_mmcif_bioassembly_data(pdb_id):
    """Make sure that the bioassembly data is the same in PDB and MMCIF files."""
    pdb_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'pdb')
    logger.debug(pdb_url)

    mmcif_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'cif')
    logger.debug(mmcif_url)

    with open_url(pdb_url) as fh:
        parser = PDBParser()
        parser.get_structure(fh)
        pdb_bioassembly_data = parser.header['bioassembly_data']

    with open_url(mmcif_url) as fh:
        sdict = mmcif2dict(fh)
        mmcif_bioassembly_data = get_mmcif_bioassembly_data(sdict, use_auth_id=True)

    # Make sure we have bioassemblies with the same ids
    assert len(pdb_bioassembly_data) == len(mmcif_bioassembly_data)
    assert not (set(pdb_bioassembly_data) ^ set(mmcif_bioassembly_data))
    for bioassembly_id in pdb_bioassembly_data:
        # Make sure the bioasembly applies to the same chains
        assert not (
            set(pdb_bioassembly_data[bioassembly_id]) ^ set(mmcif_bioassembly_data[bioassembly_id]))
        for chain_id in pdb_bioassembly_data[bioassembly_id]:
            # Make sure the transformations are the same
            pdb_transformations = pdb_bioassembly_data[bioassembly_id][chain_id].sort(
                key=lambda x: x.transformation_id)
            mmcif_transformations = mmcif_bioassembly_data[bioassembly_id][chain_id].sort(
                key=lambda x: x.transformation_id)
            assert pdb_transformations == mmcif_transformations


@parametrize("pdb_id, pdb_type, bioassembly_id", TEST_DATA['can_load_bioassembly'])
def test_can_load_bioassembly(pdb_id, pdb_type, bioassembly_id):
    url = DEFAULT_ROUTES['rcsb://'](pdb_id, pdb_type)
    structure = kmbio.PDB.load(url, bioassembly_id=bioassembly_id, use_auth_id=False)
    assert structure


# #############################################################################
# PDB_BIOASSEMBLY_FILES
# #############################################################################

with open(op.join(op.splitext(__file__)[0], 'pdb_bioassembly_files.json'), 'rt') as ifh:
    PDB_BIOASSEMBLY_FILES = json.load(ifh)


@pytest.mark.parametrize('pdb_bioassembly_file',
                         random.sample(PDB_BIOASSEMBLY_FILES, NUMBER_OF_SAMPLES))
def test_pdb_vs_pdb_ref(pdb_bioassembly_file):
    """Compare PDB bioassemblies generated by `bio.PDB` to those provided by wwPDB."""
    if pdb_bioassembly_file in [
            #
            '3lnj.pdb2.gz',  # H_SPW treated as individual atoms in the PDB
            '2xd8.pdb1.gz',  # Not sure what's going on with this one...
    ]:
        pytest.xfail("This structure is known to fail.")

    # Filenames are of the form: '{pdb_id}.pdb{bioassembly_id}.gz'
    pdb_id, bioassembly_id = re.findall('(.*)\.pdb([0-9]+)\.gz', pdb_bioassembly_file)[0]
    logger.debug("pdb_id, bioassembly_id: %s, %s", pdb_id, bioassembly_id)

    pdb_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'pdb')
    logger.debug(pdb_url)

    pdb_bioassembly_url = (
        URL + "biounit/PDB/divided/{0}/{1}".format(pdb_id[1:3], pdb_bioassembly_file))
    logger.info(pdb_bioassembly_url)

    with open_url(pdb_url) as fh:
        pdb_structure = PDBParser().get_structure(fh, bioassembly_id=bioassembly_id)

    with open_url(pdb_bioassembly_url) as fh:
        pdb_bioassembly_structure = PDBParser().get_structure(fh)

    # Chains might be in a different order, but that's ok...
    sort_structure(pdb_structure)
    sort_structure(pdb_bioassembly_structure)

    assert allequal(pdb_structure, pdb_bioassembly_structure, 1e-2)


@pytest.mark.parametrize('pdb_bioassembly_file',
                         random.sample(PDB_BIOASSEMBLY_FILES, NUMBER_OF_SAMPLES))
def test_mmcif_vs_pdb_ref(pdb_bioassembly_file):
    """Compare PDB bioassemblies generated by `bio.PDB` to those provided by wwPDB."""
    if pdb_bioassembly_file in [
            #
            '3lnj.pdb2.gz',  # H_SPW treated as individual atoms in the PDB
            '2xd8.pdb1.gz',  # Not sure what's going on with this one...
    ]:
        pytest.xfail("This structure is known to fail.")

    # Filenames are of the form: '{pdb_id}.pdb{bioassembly_id}.gz'
    pdb_id, bioassembly_id = re.findall(r'(.*)\.pdb([0-9]+)\.gz', pdb_bioassembly_file)[0]
    logger.debug("pdb_id, bioassembly_id: %s, %s", pdb_id, bioassembly_id)

    pdb_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'cif')
    logger.debug(pdb_url)

    pdb_bioassembly_url = (
        URL + "biounit/PDB/divided/{0}/{1}".format(pdb_id[1:3], pdb_bioassembly_file))
    logger.info(pdb_bioassembly_url)

    with open_url(pdb_url) as fh:
        mmcif_structure = MMCIFParser(use_auth_id=True).get_structure(
            fh, bioassembly_id=bioassembly_id)

    with open_url(pdb_bioassembly_url) as fh:
        pdb_bioassembly_structure = PDBParser().get_structure(fh)

    # Chains might be in a different order, but that's ok...
    sort_structure(mmcif_structure)
    sort_structure(pdb_bioassembly_structure)

    assert allequal(mmcif_structure, pdb_bioassembly_structure, 1e-2)


# #############################################################################
# MMCIF_BIOASSEMBLY_FILES
# #############################################################################

with open(op.join(op.splitext(__file__)[0], 'mmcif_bioassembly_files.json'), 'rt') as ifh:
    MMCIF_BIOASSEMBLY_FILES = json.load(ifh)


@pytest.mark.parametrize('mmcif_bioassembly_file',
                         random.sample(MMCIF_BIOASSEMBLY_FILES, NUMBER_OF_SAMPLES))
def test_mmcif_vs_mmcif_ref(mmcif_bioassembly_file):
    """Compare structures generated by `bio.PDB` and PyMOL from the same MMCIF file."""
    if mmcif_bioassembly_file in ['4v5s-assembly1.cif.gz']:
        pytest.xfail("This structure is known to fail.")

    # Filenames are of the form: '{pdb_id}-assembly{bioassembly_id}.cif.gz'
    pdb_id, bioassembly_id = re.findall(r'(.*)-assembly([0-9]+)\.cif\.gz',
                                        mmcif_bioassembly_file)[0]
    logger.debug("pdb_id, bioassembly_id: %s, %s", pdb_id, bioassembly_id)

    mmcif_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'cif')
    logger.debug(mmcif_url)

    mmcif_bioassembly_url = (
        URL + "biounit/mmCIF/divided/{0}/{1}".format(pdb_id[1:3], mmcif_bioassembly_file))
    logger.info(mmcif_bioassembly_url)

    with open_url(mmcif_url) as fh:
        mmcif_structure = MMCIFParser().get_structure(fh, bioassembly_id=bioassembly_id)

    with open_url(mmcif_bioassembly_url) as fh:
        mmcif_bioassembly_structure = MMCIFParser().get_structure(fh)

    assert allequal(mmcif_structure, mmcif_bioassembly_structure)