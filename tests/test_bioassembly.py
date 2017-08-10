import gzip
import logging
import os

import pytest

from kmbio.PDB import (allequal, DEFAULT_ROUTES, get_mmcif_bioassembly_data, MMCIF2Dict,
                       MMCIFParser, open_url, PDBParser, ProcessRemark350)

logger = logging.getLogger(__name__)

URL = "ftp://ftp.wwpdb.org/pub/pdb/data/"

TEST_DATA = [
    # (pdb_id, bioassembly_id)
    ('1y0x', 2),
    ('1y0o', 1),
    ('1y0y', 1),
    ('1dvf', 1),
]

PDB_IDS = [
    '2vmw',
    '1y0y',
    '4dkl',
    '1dvf',
]


@pytest.mark.parametrize("pdb_id, bioassembly_id", TEST_DATA)
def test_process_line_350(pdb_id, bioassembly_id):
    pdb_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'pdb')
    with open_url(pdb_url) as ifh:
        data = [l for l in ifh if l.startswith('REMARK 350')]
    pr350 = ProcessRemark350()
    bioassembly_data = pr350.process_lines(data)
    assert str(bioassembly_id) in bioassembly_data
    logger.debug(bioassembly_data)


@pytest.mark.parametrize("pdb_id", PDB_IDS)
def test_pdb_to_mmcif(pdb_id):
    pdb_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'pdb')
    logger.debug(pdb_url)

    mmcif_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'cif')
    logger.debug(mmcif_url)

    with open_url(pdb_url) as fh:
        parser = PDBParser()
        parser.get_structure(fh)
        pdb_bioassembly_data = parser.header['bioassembly_data']

    with open_url(mmcif_url) as fh:
        sdict = MMCIF2Dict(fh)
        mmcif_bioassembly_data = get_mmcif_bioassembly_data(sdict, use_auth_id=True)

    assert pdb_bioassembly_data == mmcif_bioassembly_data


@pytest.mark.parametrize("pdb_id, bioassembly_id", TEST_DATA)
def test_pdb_to_pdb_ref(pdb_id, bioassembly_id):
    pdb_url = DEFAULT_ROUTES['rcsb://'](pdb_id, 'pdb')
    logger.info(pdb_url)

    pdb_bioassembly_url = (
        URL + "biounit/PDB/divided/{}/{}.pdb{}.gz".format(pdb_id[1:3], pdb_id, bioassembly_id))
    logger.info(pdb_bioassembly_url)

    with open_url(pdb_url) as fh:
        mmcif_structure = PDBParser().get_structure(fh, bioassembly_id=bioassembly_id)

    with open_url(pdb_bioassembly_url) as fh:
        pdb_bioassembly_structure = PDBParser().get_structure(fh)

    assert allequal(mmcif_structure, pdb_bioassembly_structure)


@pytest.mark.parametrize("pdb_id, bioassembly_id", TEST_DATA)
def test_mmcif_to_pdb_ref(pdb_id, bioassembly_id):
    mmcif_url = (URL + "structures/divided/mmCIF/{}/{}.cif.gz".format(pdb_id[1:3], pdb_id))
    logger.info(mmcif_url)

    pdb_bioassembly_url = (
        URL + "biounit/PDB/divided/{}/{}.pdb{}.gz".format(pdb_id[1:3], pdb_id, bioassembly_id))
    logger.info(pdb_bioassembly_url)

    with open_url(mmcif_url) as fh:
        mmcif_structure = MMCIFParser(use_auth_id=True).get_structure(
            fh, bioassembly_id=bioassembly_id)

    with open_url(pdb_bioassembly_url) as fh:
        pdb_bioassembly_structure = PDBParser().get_structure(fh)

    assert allequal(mmcif_structure, pdb_bioassembly_structure)


# PDB_DATA_DIR = '/home/kimlab1/database_data/pdb/data/data/'
@pytest.mark.skipif(
    'PDB_DATA_DIR' not in os.environ,
    reason="set PDB_DATA_DIR environment variable to run this test!")
@pytest.mark.parametrize("pdb_id, bioassembly_id, use_auth_id", [(*t, tf)
                                                                 for t in TEST_DATA
                                                                 for tf in [True, False]])
def test_mmcif_to_mmcif_ref(pdb_id, bioassembly_id, use_auth_id):
    mmcif_file = (os.environ['PDB_DATA_DIR'] + "structures/divided/mmCIF/{}/{}.cif.gz".format(
        pdb_id[1:3], pdb_id))
    logger.info(mmcif_file)

    mmcif_bioassembly_file = (
        os.environ['PDB_DATA_DIR'] + "structures/divided/mmCIF/{}/{}-{}.cif".format(
            pdb_id[1:3], pdb_id, bioassembly_id))
    logger.info(mmcif_bioassembly_file)

    with gzip.open(mmcif_file, 'rt') as ifh:
        mmcif_structure = MMCIFParser(use_auth_id=False).get_structure(
            ifh, bioassembly_id=bioassembly_id)

    with open(mmcif_bioassembly_file, 'rt') as ifh:
        mmcif_bioassembly_structure = MMCIFParser(use_auth_id=False).get_structure(ifh)

    assert allequal(mmcif_structure, mmcif_bioassembly_structure)
