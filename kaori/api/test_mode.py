from fastapi import APIRouter

from kaori.config import TEST_MODE

router = APIRouter(prefix="/test-mode", tags=["test-mode"])


@router.get("/status")
async def test_mode_status():
    return {"test_mode": TEST_MODE}


@router.post("/fork")
async def fork_real_to_test():
    """Copy the real database + photos to the test location.

    Must be called while the app is running in *production* mode
    (KAORI_TEST_MODE is off).  Restart with KAORI_TEST_MODE=1
    after forking to use the test copy.
    """
    if TEST_MODE:
        return {"error": "Already in test mode. Fork from production mode."}, 400

    from kaori.database import fork_to_test
    fork_to_test()
    return {"status": "ok", "message": "Real data forked to test. Restart with KAORI_TEST_MODE=1."}
