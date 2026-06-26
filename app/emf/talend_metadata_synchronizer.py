
from app.emf.emf_id_extractor import (
    EMFIdExtractor
)

from app.emf.emf_reference_validator import (
    EMFReferenceValidator
)

from app.emf.context_reference_rebuilder import (
    ContextReferenceRebuilder
)


class TalendMetadataSynchronizer:

    def __init__(self):

        self.extractor = (
            EMFIdExtractor()
        )

        self.validator = (
            EMFReferenceValidator()
        )

        self.rebuilder = (
            ContextReferenceRebuilder()
        )

    def synchronize(

        self,
        content
    ):

        ids = self.extractor.extract_ids(
            content
        )

        errors = self.validator.validate(
            ids
        )

        return self.rebuilder.rebuild(
            content
        )
