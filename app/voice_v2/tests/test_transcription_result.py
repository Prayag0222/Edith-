from app.voice_v2.recognition.transcription_result import TranscriptionResult, TranscriptionSegment
def test_result_to_dict():
    r = TranscriptionResult("Open Chrome","en",.99,"small","cpu","int8","test",.4,1.2,
        "command",.9,"pattern",(TranscriptionSegment(0,1,"Open Chrome"),))
    d = r.to_dict()
    assert d["text"] == "Open Chrome" and d["segments"][0]["start"] == 0
