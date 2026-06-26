
class EMFReferenceValidator:

    def validate(self, ids):

        errors = []

        if not ids:

            errors.append(
                "No EMF IDs found"
            )

        return errors
