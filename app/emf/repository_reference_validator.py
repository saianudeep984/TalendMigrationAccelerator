
class RepositoryReferenceValidator:

    def validate(self, repository):

        errors = []

        if not repository.get("items"):

            errors.append(
                "No repository items found"
            )

        return errors
